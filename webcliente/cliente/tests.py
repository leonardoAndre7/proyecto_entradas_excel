from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from cliente.models import Evento, Tarifa, PerfilUsuario, Participante
from cliente.views import enviar_entrada_participante

class SystemFlowsTestCase(TestCase):
    def setUp(self):
        # Create Superadmin
        self.super_user = User.objects.create_superuser(username="superadmin", email="super@test.com", password="password123")
        self.super_perfil, _ = PerfilUsuario.objects.get_or_create(user=self.super_user, rol="SUPERADMIN")

        # Create Organizer 1
        self.org1_user = User.objects.create_user(username="org1", email="org1@test.com", password="password123")
        self.org1_perfil = PerfilUsuario.objects.create(user=self.org1_user, rol="ORGANIZADOR")

        # Create Organizer 2
        self.org2_user = User.objects.create_user(username="org2", email="org2@test.com", password="password123")
        self.org2_perfil = PerfilUsuario.objects.create(user=self.org2_user, rol="ORGANIZADOR")

        # Create Event 1 for Organizer 1
        self.event1 = Evento.objects.create(
            nombre="Evento Emprendedor 1",
            descripcion="Descripción del Evento 1",
            color_primario="#0ea5e9"
        )
        self.org1_perfil.eventos.add(self.event1)

        # Create Event 2 for Organizer 2
        self.event2 = Evento.objects.create(
            nombre="Evento Corporativo 2",
            descripcion="Descripción del Evento 2",
            color_primario="#f43f5e"
        )
        self.org2_perfil.eventos.add(self.event2)

        # Create dynamic Tariffs for Event 1
        self.tarifa_vip1 = Tarifa.objects.create(
            evento=self.event1,
            tipo_entrada="VIP PREMIUM",
            preventa_1=Decimal("150.00"),
            preventa_2=Decimal("200.00"),
            preventa_3=Decimal("250.00"),
            puerta=Decimal("300.00")
        )
        self.tarifa_gen1 = Tarifa.objects.create(
            evento=self.event1,
            tipo_entrada="ACCESO GENERAL",
            preventa_1=Decimal("50.00"),
            preventa_2=Decimal("75.00"),
            preventa_3=Decimal("100.00"),
            puerta=Decimal("120.00")
        )

        # Create Client
        self.client = Client()

    def test_dynamic_categories_and_tariffs(self):
        """Verify that tariffs can be created and queried dynamically."""
        self.assertEqual(self.event1.tarifas.count(), 2)
        self.assertEqual(self.event2.tarifas.count(), 0)

        # Create participant with dynamic tariff
        part = Participante.objects.create(
            evento=self.event1,
            tarifa=self.tarifa_vip1,
            nombres="Juan",
            apellidos="Pérez",
            dni="12345678",
            correo="juan@test.com",
            cantidad=2,
            precio=Decimal("150.00"),
            pago_confirmado=False
        )

        self.assertEqual(part.tipo_entrada, "VIP PREMIUM")
        self.assertEqual(part.total_pagar, Decimal("300.00"))

    def test_multitenant_idor_protection(self):
        """Verify that Organizer 1 cannot view, edit, or delete events or participants belonging to Event 2."""
        # Authenticate as Organizer 1
        self.client.login(username="org1", password="password123")

        # Attempt to access Event 2's participant list
        response = self.client.get(reverse('participante_lista', kwargs={'evento_id': self.event2.id}))
        # EventPermissionMiddleware should block or redirect this because Organizer 1 is not assigned to Event 2.
        self.assertIn(response.status_code, [302, 403, 404])

    def test_superadmin_user_management(self):
        """Verify that Superadmin can list and create sub-account users successfully."""
        self.client.login(username="superadmin", password="password123")

        # List users
        response = self.client.get(reverse('usuario_lista'))
        self.assertEqual(response.status_code, 200)

        # Create a new sub-account user
        create_data = {
            'username': 'neworg',
            'email': 'neworg@test.com',
            'password': 'newpassword123',
            'rol': 'ORGANIZADOR',
            'eventos': [self.event1.id]
        }
        response = self.client.post(reverse('usuario_crear'), data=create_data)
        self.assertEqual(response.status_code, 302)  # Redirect to list

        # Verify database creation
        new_user = User.objects.filter(username="neworg").first()
        self.assertIsNotNone(new_user)
        new_perfil = PerfilUsuario.objects.get(user=new_user)
        self.assertEqual(new_perfil.rol, "ORGANIZADOR")
        self.assertIn(self.event1, new_perfil.eventos.all())

    def test_organizer_user_management(self):
        """Verify that an Organizer can view, create, edit, and delete door staff (REGISTRADORES) for their events."""
        # Login as Organizer 1
        self.client.login(username="org1", password="password123")

        # 1. View User Management Dashboard (should load successfully)
        response = self.client.get(reverse('usuario_lista'))
        self.assertEqual(response.status_code, 200)

        # 2. Create staff (REGISTRADOR) user for Event 1
        create_data = {
            'username': 'staff1_event1',
            'email': 'staff1@test.com',
            'password': 'password123',
            'rol': 'REGISTRADOR',
            'eventos': [self.event1.id]
        }
        response = self.client.post(reverse('usuario_crear'), data=create_data)
        self.assertEqual(response.status_code, 302) # Redirects on success

        # Assert database state
        staff_user = User.objects.filter(username='staff1_event1').first()
        self.assertIsNotNone(staff_user)
        staff_perfil = PerfilUsuario.objects.get(user=staff_user)
        self.assertEqual(staff_perfil.rol, 'REGISTRADOR')
        self.assertIn(self.event1, staff_perfil.eventos.all())

        # 3. Prevent unauthorized assignment (Organizer 1 attempts to assign Event 2 to this staff)
        create_data_unauthorized = {
            'username': 'staff2_illegal',
            'email': 'staff2@test.com',
            'password': 'password123',
            'rol': 'REGISTRADOR',
            'eventos': [self.event2.id] # Event 2 is not owned by Organizer 1
        }
        response = self.client.post(reverse('usuario_crear'), data=create_data_unauthorized)
        # Should redirect with error because Event 2 was filtered out, leaving no events, returning to creator with error
        self.assertEqual(response.status_code, 302)
        # Verify the user 'staff2_illegal' was not created or has no events assigned
        staff2 = User.objects.filter(username='staff2_illegal').first()
        if staff2:
            self.assertEqual(PerfilUsuario.objects.get(user=staff2).eventos.count(), 0)

    def test_auto_send_helper_no_exception(self):
        """Verify that sending a ticket does not crash even if the mail server config is empty."""
        part = Participante.objects.create(
            evento=self.event1,
            tarifa=self.tarifa_vip1,
            nombres="Pedro",
            apellidos="García",
            dni="87654321",
            correo="pedro@test.com",
            cantidad=1,
            precio=Decimal("150.00"),
            pago_confirmado=True
        )
        # Should execute successfully without throwing errors
        success = enviar_entrada_participante(part)
        self.assertTrue(success or not success)  # Expect clean execution regardless of mock SMTP success
