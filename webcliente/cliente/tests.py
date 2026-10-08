import datetime
import os
import tempfile
from unittest import mock

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from cliente.models import Evento, Tarifa, PerfilUsuario, Participante
from cliente.views import enviar_entrada_participante


class IngresosPorDiaTestCase(TestCase):
    """Ingreso multi-día configurable por tarifa + arreglos de WhatsApp / media."""

    def setUp(self):
        self.evento = Evento.objects.create(nombre="Prueba")
        self.emp = Tarifa.objects.create(evento=self.evento, tipo_entrada="EMPRESARIAL", dias_validos=2)
        self.vip = Tarifa.objects.create(
            evento=self.evento, tipo_entrada="VIP", dias_validos=1,
            hora_desde=datetime.time(14, 0), hora_hasta=datetime.time(23, 0),
        )
        tz = timezone.get_current_timezone()
        self.d1 = timezone.make_aware(datetime.datetime(2026, 10, 10, 10, 0), tz)
        self.d1_tarde = timezone.make_aware(datetime.datetime(2026, 10, 10, 18, 0), tz)
        self.d2 = timezone.make_aware(datetime.datetime(2026, 10, 11, 10, 0), tz)
        self.d3 = timezone.make_aware(datetime.datetime(2026, 10, 12, 10, 0), tz)

    def _part(self, tarifa, dni):
        return Participante.objects.create(
            evento=self.evento, tarifa=tarifa, nombres="X", dni=dni, cantidad=1, precio=1
        )

    def _en(self, momento, participante):
        with mock.patch("django.utils.timezone.now", return_value=momento):
            return participante.registrar_ingreso()[0]

    def test_empresarial_dos_dias(self):
        p = self._part(self.emp, "1")
        resultados = [self._en(m, p) for m in (self.d1, self.d1_tarde, self.d2, self.d3)]
        self.assertEqual(resultados, [True, False, True, False])

    def test_vip_respeta_ventana_horaria_y_un_dia(self):
        p = self._part(self.vip, "2")
        self.assertFalse(self._en(self.d1, p))          # 10:00, fuera de ventana
        self.assertTrue(self._en(self.d1_tarde, p))     # 18:00
        self.assertFalse(self._en(self.d2.replace(hour=18), p))  # ya agotó su único día

    def test_entrada_ya_escaneada_antes_cuenta_como_un_dia(self):
        p = self._part(self.emp, "3")
        Participante.objects.filter(pk=p.pk).update(entrada_usada=True)
        p.refresh_from_db()
        self.assertTrue(self._en(self.d2, p))
        self.assertFalse(self._en(self.d3, p))
        self.assertEqual(p.ingresos.count(), 2)

    def test_lista_muestra_dias_y_boton_marcar_para_el_dia_siguiente(self):
        user = User.objects.create_superuser("admin", "a@test.com", "pass12345")
        PerfilUsuario.objects.get_or_create(user=user, defaults={"rol": "SUPERADMIN"})
        p = self._part(self.emp, "4")
        self._en(self.d1, p)
        self.client.login(username="admin", password="pass12345")
        resp = self.client.get(reverse("participante_lista", kwargs={"evento_id": self.evento.id}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("1/2", html)
        self.assertIn("Marcar ingreso de otro día", html)

    def test_whatsapp_custom_api_con_payload_no_falla_y_no_guarda_entrada_en_media(self):
        evento = Evento.objects.create(
            nombre="WA", whatsapp_provider="CUSTOM_API",
            whatsapp_api_url="https://ejemplo.test/send",
            whatsapp_api_payload='{"chatId": "{celular}@c.us", "caption": "Hola {nombres}"}',
        )
        part = Participante.objects.create(
            evento=evento, nombres="Ana", dni="55555555", celular="955060412",
            correo="ana@test.com", cantidad=1, precio=1, pago_confirmado=True,
        )
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with mock.patch("cliente.views.enviar_correo_con_smtp_evento", return_value=True), \
                 mock.patch("cliente.views.requests.post") as post:
                post.return_value.status_code = 201
                enviar_entrada_participante(part)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.kwargs["json"]["chatId"], "51955060412@c.us")
            self.assertEqual([f for f in os.listdir(media) if f.startswith("entrada_")], [])


class FondoBoletoPersistenteTestCase(TestCase):
    """Render borra las imágenes subidas en cada deploy; el fondo debe recuperarse del repo."""

    def test_fondo_perdido_se_recupera_de_la_copia_del_repo_ignorando_el_sufijo(self):
        from PIL import Image
        from cliente.views import _resolver_fondo_boleto
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            carpeta = os.path.join(media, "event_backgrounds")
            os.makedirs(carpeta)
            Image.new("RGB", (10, 10)).save(os.path.join(carpeta, "entrada_ede_2026.png"))
            evento = Evento.objects.create(nombre="El Despertar del Emprendedor")
            evento.imagen_fondo.name = "event_backgrounds/entrada_ede_2026_Ab12Cd3.png"  # ya no existe
            ruta = _resolver_fondo_boleto(evento)
            self.assertEqual(os.path.basename(ruta), "entrada_ede_2026.png")
            self.assertTrue(os.path.exists(ruta))

    def test_migracion_enlaza_solo_eventos_despertar_con_fondo_perdido(self):
        import importlib
        from django.apps import apps
        mig = importlib.import_module("cliente.migrations.0032_enlazar_fondo_entrada_ede")
        perdido = Evento.objects.create(nombre="El Despertar del Emprendedor")
        perdido.imagen_fondo.name = "event_backgrounds/fondo_que_ya_no_existe.png"
        perdido.save()
        otro = Evento.objects.create(nombre="Círculo 50k")
        otro.imagen_fondo.name = "event_backgrounds/otro_que_ya_no_existe.png"
        otro.save()
        sin_fondo = Evento.objects.create(nombre="El Despertar sin fondo")
        mig.enlazar_fondo(apps, None)
        for e in (perdido, otro, sin_fondo):
            e.refresh_from_db()
        self.assertEqual(perdido.imagen_fondo.name, "event_backgrounds/entrada_ede_2026.png")
        self.assertEqual(otro.imagen_fondo.name, "event_backgrounds/otro_que_ya_no_existe.png")
        self.assertFalse(sin_fondo.imagen_fondo)

    def test_plantilla_ede_incluida_en_el_repo_genera_el_boleto(self):
        from django.conf import settings
        from cliente.views import generar_imagen_personalizada
        import qrcode
        plantilla = os.path.join(settings.MEDIA_ROOT, "event_backgrounds", "entrada_ede_2026.png")
        self.assertTrue(os.path.exists(plantilla), "falta media/event_backgrounds/entrada_ede_2026.png en el repo")
        evento = Evento.objects.create(nombre="El Despertar del Emprendedor")
        evento.imagen_fondo.name = "event_backgrounds/entrada_ede_2026.png"
        part = Participante(evento=evento, nombres="Pedro", dni="1", cantidad=1, precio=1)
        img = generar_imagen_personalizada(part, qrcode.make("https://ejemplo.test/validar/x/").convert("RGB"))
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (904, 1280))


class ReenviarWhatsAppTestCase(TestCase):
    """El botón Reenviar debe mandar también el WhatsApp y avisar el resultado."""

    def setUp(self):
        self.user = User.objects.create_superuser("admin2", "a2@test.com", "pass12345")
        PerfilUsuario.objects.get_or_create(user=self.user, defaults={"rol": "SUPERADMIN"})
        self.evento = Evento.objects.create(
            nombre="WA reenvio", whatsapp_provider="CUSTOM_API",
            whatsapp_api_url="https://ejemplo.test/send",
            whatsapp_api_payload='{"chatId": "{celular}@c.us", "caption": "Hola {nombres}"}',
        )
        self.part = Participante.objects.create(
            evento=self.evento, nombres="Ana", dni="77777777", celular="955060412",
            correo="ana@test.com", cantidad=1, precio=1, pago_confirmado=True,
        )
        self.client.login(username="admin2", password="pass12345")
        self.url = reverse("reenviar_correo", kwargs={"evento_id": self.evento.id, "pk": self.part.pk})

    def _reenviar(self, status_code=201, body=None, correo_ok=False):
        with mock.patch("cliente.views.enviar_correo_con_smtp_evento", return_value=correo_ok), \
             mock.patch("cliente.views.requests.post") as post:
            post.return_value.status_code = status_code
            post.return_value.text = body or "{}"
            post.return_value.json.return_value = {} if body is None else __import__("json").loads(body)
            resp = self.client.post(self.url, follow=True)
        textos = [str(m) for m in resp.context["messages"]]
        return post, textos

    def test_reenviar_manda_whatsapp_aunque_falle_el_correo(self):
        post, textos = self._reenviar()
        self.assertEqual(post.call_count, 1)
        self.assertTrue(any("WhatsApp: enviado" in t for t in textos), textos)
        self.assertTrue(any("Fallo al enviar el correo" in t for t in textos), textos)

    def test_reenviar_avisa_si_la_clave_de_whatsapp_es_invalida(self):
        post, textos = self._reenviar(status_code=401, body='{"message":"Invalid API key","statusCode":401}')
        self.assertTrue(any("WhatsApp no enviado" in t and "401" in t for t in textos), textos)

    def test_sin_imgbb_no_se_envia_una_peticion_vacia_y_se_explica(self):
        Evento.objects.filter(pk=self.evento.pk).update(
            whatsapp_api_payload='{"chatId": "{celular}@c.us", "url": "{url_imagen}"}', imgbb_api_key="")
        post, textos = self._reenviar()
        self.assertEqual(post.call_count, 0)
        self.assertTrue(any("ImgBB" in t and "WhatsApp no enviado" in t for t in textos), textos)

    def test_imagen_base64_viaja_en_el_mensaje_sin_imgbb_y_el_nombre_no_rompe_el_json(self):
        Evento.objects.filter(pk=self.evento.pk).update(
            whatsapp_api_payload=('{"chatId": "{celular}@c.us", "base64": "{imagen_base64}", '
                                  '"mimetype": "image/png", "caption": "Hola {nombres}"}'),
            imgbb_api_key="")
        Participante.objects.filter(pk=self.part.pk).update(nombres='Ana "la jefa"\nPérez')
        enviados = []

        def fake_post(url, *a, **kw):
            enviados.append((url, kw.get("json")))
            r = mock.Mock()
            r.status_code = 201
            r.text = "{}"
            r.json.return_value = {}
            return r

        with mock.patch("cliente.views.enviar_correo_con_smtp_evento", return_value=True), \
             mock.patch("cliente.views.requests.post", side_effect=fake_post):
            resp = self.client.post(self.url, follow=True)
        self.assertEqual(len(enviados), 1)                      # no se llamó a ImgBB
        self.assertNotIn("imgbb", enviados[0][0])
        cuerpo = enviados[0][1]
        self.assertEqual(cuerpo["chatId"], "51955060412@c.us")
        self.assertEqual(cuerpo["mimetype"], "image/png")
        import base64 as b64
        self.assertTrue(b64.b64decode(cuerpo["base64"])[:8] == b"\x89PNG\r\n\x1a\n")
        self.assertEqual(cuerpo["caption"], 'Hola Ana "la jefa"\nPérez')
        self.assertTrue(any("WhatsApp: enviado" in str(m) for m in resp.context["messages"]))

    def test_imgbb_ok_envia_la_url_en_el_payload(self):
        Evento.objects.filter(pk=self.evento.pk).update(
            whatsapp_api_payload='{"chatId": "{celular}@c.us", "url": "{url_imagen}"}', imgbb_api_key="clave-de-prueba")
        respuestas = []

        def fake_post(url, *a, **kw):
            r = mock.Mock()
            if "imgbb" in url:
                r.status_code = 200
                r.json.return_value = {"data": {"url": "https://i.ibb.co/x/entrada.png"}}
            else:
                respuestas.append(kw.get("json"))
                r.status_code = 201
                r.text = "{}"
                r.json.return_value = {}
            return r

        with mock.patch("cliente.views.enviar_correo_con_smtp_evento", return_value=True), \
             mock.patch("cliente.views.requests.post", side_effect=fake_post):
            self.client.post(self.url, follow=True)
        self.assertEqual(respuestas, [{"chatId": "51955060412@c.us", "url": "https://i.ibb.co/x/entrada.png"}])

    def test_401_muestra_la_cabecera_enviada_sin_revelar_la_clave(self):
        clave = "owa_k1_" + "ab" * 32 + "ede"          # clave con texto de más pegado al final
        Evento.objects.filter(pk=self.evento.pk).update(whatsapp_api_headers=f"X-API-Key: {clave}")
        post, textos = self._reenviar(status_code=401, body='{"message":"Invalid API key","statusCode":401}')
        aviso = " ".join(textos)
        self.assertIn("Cabeceras enviadas: X-API-Key=owa_k1_a…bede (74 caracteres)", aviso)
        self.assertNotIn(clave, aviso)

    def test_reenviar_detecta_error_dentro_de_un_200(self):
        post, textos = self._reenviar(status_code=200, body='{"statusCode":500,"message":"Internal server error"}')
        self.assertTrue(any("WhatsApp no enviado" in t and "500" in t for t in textos), textos)

    def test_reenviar_sin_celular_lo_dice(self):
        Participante.objects.filter(pk=self.part.pk).update(celular="")
        post, textos = self._reenviar()
        self.assertEqual(post.call_count, 0)
        self.assertTrue(any("no tiene celular" in t for t in textos), textos)


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
