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


@override_settings(API_KEY="clave-segura-de-prueba-123")
class ApiRegistrarParticipanteTestCase(TestCase):
    """Entrada de ventas desde la hoja de Google (Apps Script) por la API."""

    def setUp(self):
        import json
        self.json = json
        self.evento = Evento.objects.create(nombre="EDE 2026")
        self.emp = Tarifa.objects.create(evento=self.evento, tipo_entrada="EMPRESARIAL", dias_validos=2,
                                         preventa_1=Decimal("1999"))
        Tarifa.objects.create(evento=self.evento, tipo_entrada="EMPRENDEDOR", preventa_1=Decimal("150"))
        self.url = reverse("api_registrar_participante")

    def _post(self, datos, clave="clave-segura-de-prueba-123"):
        h = {"HTTP_X_API_KEY": clave} if clave is not None else {}
        return self.client.post(self.url, self.json.dumps(datos), content_type="application/json", **h)

    def _venta(self, **extra):
        d = {"evento_id": self.evento.id, "nombres": "  Ana   Pérez ", "dni": "12345678",
             "celular": "955060412", "correo": "ANA@Test.com ", "tipo_entrada": "empresarial",
             "precio_final": 1999, "vendedor": "Daniel", "metodo_pago": "Yape",
             "voucher_url": "https://drive.google.com/open?id=abc", "notas": "Separacion",
             "referencia": "fila-7", "estricto": True}
        d.update(extra)
        return d

    def test_crea_el_participante_con_los_datos_de_la_hoja_y_normaliza_textos(self):
        r = self._post(self._venta())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        p = Participante.objects.get(pk=r.json()["id"])
        self.assertEqual(p.nombres, "Ana Pérez")                    # espacios sobrantes quitados
        self.assertEqual(p.correo, "ana@test.com")                  # en minúsculas
        self.assertEqual(p.tarifa, self.emp)                        # "empresarial" -> EMPRESARIAL (sin importar mayúsculas)
        self.assertEqual(p.metodo_pago, "Yape")
        self.assertEqual(p.voucher_url, "https://drive.google.com/open?id=abc")
        self.assertEqual(p.notas, "Separacion")
        self.assertFalse(p.pago_confirmado)                         # contabilidad lo valida en el sistema

    def test_reintentar_la_misma_fila_no_crea_otro_participante(self):
        a = self._post(self._venta()).json()
        b = self._post(self._venta()).json()
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(b["duplicado"])
        self.assertEqual(Participante.objects.count(), 1)

    def test_dni_repetido_se_rechaza(self):
        self._post(self._venta())
        r = self._post(self._venta(referencia="fila-8"))
        self.assertEqual(r.status_code, 409)

    def test_modo_estricto_rechaza_una_tarifa_inexistente_y_lista_las_validas(self):
        r = self._post(self._venta(tipo_entrada="Platino"))
        self.assertEqual(r.status_code, 400)
        self.assertCountEqual(r.json()["tarifas_disponibles"], ["EMPRESARIAL", "EMPRENDEDOR"])
        self.assertEqual(Participante.objects.count(), 0)

    def test_sin_modo_estricto_se_mantiene_el_comportamiento_anterior(self):
        r = self._post(self._venta(tipo_entrada="Platino", estricto=False))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(Participante.objects.get(pk=r.json()["id"]).tarifa)

    def test_clave_incorrecta_o_ausente_se_rechaza(self):
        self.assertEqual(self._post(self._venta(), clave="otra").status_code, 403)
        self.assertEqual(self._post(self._venta(), clave=None).status_code, 403)
        self.assertEqual(Participante.objects.count(), 0)

    def test_sin_nombre_se_rechaza(self):
        self.assertEqual(self._post(self._venta(nombres="   ")).status_code, 400)

    @override_settings(API_KEY="cambiar-en-produccion-render")
    def test_la_clave_por_defecto_del_repositorio_no_abre_la_api(self):
        r = self._post(self._venta(), clave="cambiar-en-produccion-render")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(Participante.objects.count(), 0)

    @override_settings(API_KEY="clave-del-bot", API_KEYS_EXTRA="clave-hoja-ventas, otra-clave")
    def test_acepta_la_clave_principal_y_las_adicionales_sin_romper_al_bot(self):
        self.assertEqual(self._post(self._venta(dni="1", referencia="a"), clave="clave-del-bot").status_code, 200)
        self.assertEqual(self._post(self._venta(dni="2", referencia="b"), clave="clave-hoja-ventas").status_code, 200)
        self.assertEqual(self._post(self._venta(dni="3", referencia="c"), clave="otra-clave").status_code, 200)
        self.assertEqual(self._post(self._venta(dni="4", referencia="d"), clave="no-es-ninguna").status_code, 403)
        self.assertEqual(Participante.objects.count(), 3)

    @override_settings(API_KEY="clave-del-bot", API_KEYS_EXTRA=" , cambiar-en-produccion-render,")
    def test_las_claves_vacias_o_por_defecto_en_las_adicionales_no_abren_la_api(self):
        for clave in ("", "cambiar-en-produccion-render"):
            self.assertEqual(self._post(self._venta(), clave=clave).status_code, 403)
        self.assertEqual(Participante.objects.count(), 0)

    @override_settings(API_KEY="")
    def test_sin_clave_configurada_la_api_queda_cerrada(self):
        self.assertEqual(self._post(self._venta(), clave="").status_code, 503)

    def test_enviar_entrada_solo_si_el_pago_viene_confirmado(self):
        with mock.patch("cliente.views.enviar_entrada_participante", return_value=True) as envio:
            r = self._post(self._venta(enviar_entrada=True))                         # sin pago confirmado
            self.assertNotIn("entrada_enviada", r.json())
            self.assertEqual(envio.call_count, 0)
            r = self._post(self._venta(enviar_entrada=True, pago_confirmado=True, dni="999", referencia="f9"))
            self.assertTrue(r.json()["entrada_enviada"])
            self.assertEqual(envio.call_count, 1)

    def test_el_panel_muestra_el_enlace_al_comprobante(self):
        user = User.objects.create_superuser("adm6", "a6@test.com", "pass12345")
        PerfilUsuario.objects.get_or_create(user=user, defaults={"rol": "SUPERADMIN"})
        self.client.login(username="adm6", password="pass12345")
        self._post(self._venta())
        resp = self.client.get(reverse("participante_lista", kwargs={"evento_id": self.evento.id}))
        self.assertContains(resp, "https://drive.google.com/open?id=abc")
        self.assertContains(resp, "Asesor: Daniel")


class VigenciaYMotivosTestCase(TestCase):
    """Entradas válidas solo el 14 y 15 de noviembre y pantallas que explican el rechazo."""

    def setUp(self):
        self.user = User.objects.create_superuser("adm5", "a5@test.com", "pass12345")
        PerfilUsuario.objects.get_or_create(user=self.user, defaults={"rol": "SUPERADMIN"})
        self.client.login(username="adm5", password="pass12345")
        self.evento = Evento.objects.create(nombre="EDE 2026")
        self.emp = Tarifa.objects.create(
            evento=self.evento, tipo_entrada="EMPRESARIAL", dias_validos=2,
            fecha_desde=datetime.date(2026, 11, 14), fecha_hasta=datetime.date(2026, 11, 15))
        self.tz = timezone.get_current_timezone()

    def _en(self, dia, hora=10, minuto=0):
        return timezone.make_aware(datetime.datetime(2026, 11, dia, hora, minuto), self.tz)

    def _part(self, tarifa=None, dni="1"):
        return Participante.objects.create(evento=self.evento, tarifa=tarifa or self.emp, nombres="Ana",
                                           dni=dni, cantidad=1, precio=1)

    def _escanear(self, p, momento):
        with mock.patch("cliente.models.ahora_actual", return_value=momento):
            return self.client.get(reverse("validar_entrada", kwargs={"token": p.token}))

    def test_empresarial_vale_el_14_y_el_15_de_noviembre_y_no_otros_dias(self):
        p = self._part()
        def intento(m):
            with mock.patch("cliente.models.ahora_actual", return_value=m):
                return p.registrar_ingreso(), p.ultimo_motivo
        (ok, msg), motivo = intento(self._en(13))
        self.assertFalse(ok); self.assertEqual(motivo, "fuera_de_fecha"); self.assertIn("14/11/2026", msg)
        self.assertTrue(intento(self._en(14))[0][0])           # día 1
        (ok, _), motivo = intento(self._en(14, 18))
        self.assertFalse(ok); self.assertEqual(motivo, "duplicado")
        self.assertTrue(intento(self._en(15))[0][0])           # día 2
        (ok, msg), motivo = intento(self._en(16))
        self.assertFalse(ok); self.assertEqual(motivo, "fuera_de_fecha"); self.assertIn("15/11/2026", msg)

    def test_vip_de_un_dia_elige_cualquiera_de_los_dos_dias_y_luego_se_agota(self):
        vip = Tarifa.objects.create(evento=self.evento, tipo_entrada="VIP", dias_validos=1,
                                    fecha_desde=datetime.date(2026, 11, 14), fecha_hasta=datetime.date(2026, 11, 15))
        p = self._part(vip, "2")
        with mock.patch("cliente.models.ahora_actual", return_value=self._en(15)):
            self.assertTrue(p.registrar_ingreso()[0])
        with mock.patch("cliente.models.ahora_actual", return_value=self._en(14)):   # ya usó su único día
            ok, _ = p.registrar_ingreso()
        self.assertFalse(ok); self.assertEqual(p.ultimo_motivo, "agotado")

    def test_pantalla_fuera_de_horario_no_dice_boleto_duplicado(self):
        Tarifa.objects.filter(pk=self.emp.pk).update(hora_desde=datetime.time(10, 0))
        p = self._part()
        resp = self._escanear(p, self._en(14, 8, 30))                   # 8:30, antes de las 10:00
        self.assertContains(resp, "FUERA DE HORARIO")
        self.assertContains(resp, "Aún no ha ingresado")
        self.assertNotContains(resp, "BOLETO DUPLICADO")
        self.assertFalse(p.ingresos.exists())                           # y no quedó registrado como ingresado

    def test_pantalla_fuera_de_fecha(self):
        p = self._part()
        resp = self._escanear(p, self._en(1))
        self.assertContains(resp, "FUERA DE FECHA")
        self.assertContains(resp, "14/11/2026")

    def test_pantalla_duplicado_real_sigue_diciendo_boleto_duplicado(self):
        p = self._part()
        self._escanear(p, self._en(14, 10))
        resp = self._escanear(p, self._en(14, 12))
        self.assertContains(resp, "BOLETO DUPLICADO")

    def test_formulario_guarda_y_muestra_las_fechas_de_vigencia(self):
        url = reverse("evento_editar", kwargs={"pk": self.evento.pk})
        html = self.client.get(url).content.decode()
        import re
        estado = re.search(r'name="_estado_evento" value="([0-9a-f]{40})"', html).group(1)
        self.client.post(url, {
            "_estado_evento": estado, "nombre": "EDE 2026", "descripcion": "", "aforo_maximo": "1000",
            "limite_entradas_persona": "5", "color_primario": "#7b1fa2",
            "tariff_id": [str(self.emp.pk)], "tariff_name": ["EMPRESARIAL"], "tariff_p1": ["0"],
            "tariff_p2": ["0"], "tariff_p3": ["0"], "tariff_puerta": ["0"], "tariff_dias": ["2"],
            "tariff_hdesde": [""], "tariff_hhasta": [""],
            "tariff_fdesde": ["2026-11-14"], "tariff_fhasta": ["2026-11-16"],
        })
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.fecha_hasta, datetime.date(2026, 11, 16))
        html = self.client.get(url).content.decode()
        self.assertIn('value="2026-11-14"', html)
        self.assertIn('value="2026-11-16"', html)


class EstadoWhatsAppTestCase(TestCase):
    """La luz de WhatsApp del panel avisa a tiempo si OpenWA, la clave o la sesión fallan."""

    def setUp(self):
        self.user = User.objects.create_superuser("adm4", "a4@test.com", "pass12345")
        PerfilUsuario.objects.get_or_create(user=self.user, defaults={"rol": "SUPERADMIN"})
        self.client.login(username="adm4", password="pass12345")
        self.evento = Evento.objects.create(
            nombre="WA estado", whatsapp_provider="CUSTOM_API",
            whatsapp_api_url="https://ejemplo.test/api/sessions/abc-123/messages/send-image",
            whatsapp_api_headers="X-API-Key: owa_k1_PRUEBA",
        )
        self.url = reverse("estado_whatsapp", kwargs={"evento_id": self.evento.id})

    def _consultar(self, status=200, cuerpo=None, error=None):
        with mock.patch("cliente.views.requests.get") as get:
            if error:
                get.side_effect = error
            else:
                get.return_value.status_code = status
                get.return_value.json.return_value = cuerpo or {}
            resp = self.client.get(self.url)
        return resp.json(), get

    def test_sesion_ready_es_conectado_y_usa_la_url_y_clave_del_evento(self):
        d, get = self._consultar(cuerpo={"status": "ready"})
        self.assertTrue(d["ok"])
        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://ejemplo.test/api/sessions/abc-123")
        self.assertEqual(kwargs["headers"]["X-API-Key"], "owa_k1_PRUEBA")

    def test_sesion_desconectada(self):
        d, _ = self._consultar(cuerpo={"status": "disconnected"})
        self.assertFalse(d["ok"])
        self.assertIn("disconnected", d["detalle"])

    def test_clave_invalida(self):
        d, _ = self._consultar(status=401)
        self.assertEqual(d["estado"], "clave_invalida")

    def test_sesion_inexistente(self):
        d, _ = self._consultar(status=404)
        self.assertEqual(d["estado"], "sesion_inexistente")

    def test_openwa_apagado(self):
        d, _ = self._consultar(error=ConnectionError("sin red"))
        self.assertEqual(d["estado"], "sin_respuesta")
        self.assertFalse(d["ok"])

    def test_evento_sin_whatsapp_configurado(self):
        Evento.objects.filter(pk=self.evento.pk).update(whatsapp_provider="INACTIVE")
        d, get = self._consultar()
        self.assertIsNone(d["ok"])
        self.assertEqual(get.call_count, 0)

    def test_el_panel_muestra_la_luz_de_estado(self):
        resp = self.client.get(reverse("participante_lista", kwargs={"evento_id": self.evento.id}))
        self.assertContains(resp, 'id="wa-estado"')
        self.assertContains(resp, self.url)

    def test_organizador_de_otro_evento_no_puede_consultarlo(self):
        otro = User.objects.create_user("org9", "o9@test.com", "pass12345")
        PerfilUsuario.objects.create(user=otro, rol="ORGANIZADOR")
        self.client.logout()
        self.client.login(username="org9", password="pass12345")
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 403))


class RespaldoArchivosTestCase(TestCase):
    """Los archivos subidos se copian a la base de datos y se restauran si Render borra el disco."""

    def _png(self):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (20, 20), (200, 30, 30)).save(buf, format="PNG")
        return buf.getvalue()

    def test_subir_logo_lo_respalda_y_se_restaura_si_el_disco_se_borra(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from cliente.models import ArchivoMedia
        from cliente import media_respaldo
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            ev = Evento.objects.create(nombre="E")
            ev.logo = SimpleUploadedFile("logo.png", self._png(), content_type="image/png")
            ev.save()
            ruta = ev.logo.name
            self.assertTrue(os.path.exists(os.path.join(media, ruta)))
            self.assertTrue(ArchivoMedia.objects.filter(ruta=ruta).exists())       # respaldado
            os.remove(os.path.join(media, ruta))                                   # "Render borra el disco"
            self.assertEqual(media_respaldo.restaurar_todo(), 1)
            self.assertEqual(open(os.path.join(media, ruta), "rb").read(), self._png())

    def test_fondo_del_boleto_se_restaura_desde_la_base_de_datos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from cliente.views import _resolver_fondo_boleto
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            ev = Evento.objects.create(nombre="E2")
            ev.imagen_fondo = SimpleUploadedFile("fondo.png", self._png(), content_type="image/png")
            ev.save()
            ruta = os.path.join(media, ev.imagen_fondo.name)
            os.remove(ruta)
            self.assertEqual(os.path.normpath(_resolver_fondo_boleto(ev)), os.path.normpath(ruta))
            self.assertTrue(os.path.exists(ruta))

    def test_fondo_perdido_sin_copia_usa_la_plantilla_del_repo_y_se_enlaza(self):
        """Caso real: el fondo subido desde el panel se borró y no hay copia en la base de datos."""
        from cliente.views import _resolver_fondo_boleto, generar_imagen_personalizada
        import qrcode
        ev = Evento.objects.create(nombre="El Despertar del Emprendedor")
        ev.imagen_fondo.name = "event_backgrounds/subido_desde_el_panel_Ab12Cd3.png"   # ya no existe
        ev.save()
        ruta = _resolver_fondo_boleto(ev)
        self.assertTrue(ruta.replace("\\", "/").endswith("event_backgrounds/entrada_ede_2026.png"))
        ev.refresh_from_db()
        self.assertEqual(ev.imagen_fondo.name, "event_backgrounds/entrada_ede_2026.png")   # quedó enlazada
        part = Participante(evento=ev, nombres="Pedro", dni="1", cantidad=1, precio=1)
        self.assertIsNotNone(generar_imagen_personalizada(part, qrcode.make("x").convert("RGB")))

    def test_enlazar_plantillas_faltantes_solo_toca_eventos_con_plantilla(self):
        from cliente import media_respaldo
        a = Evento.objects.create(nombre="El Despertar del Emprendedor")
        a.imagen_fondo.name = "event_backgrounds/perdido.png"
        a.save()
        b = Evento.objects.create(nombre="Círculo 50k")
        b.imagen_fondo.name = "event_backgrounds/otro_perdido.png"
        b.save()
        self.assertEqual(media_respaldo.enlazar_plantillas_faltantes(), 1)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.imagen_fondo.name, "event_backgrounds/entrada_ede_2026.png")
        self.assertEqual(b.imagen_fondo.name, "event_backgrounds/otro_perdido.png")

    def test_comprobante_de_pago_se_respalda(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from cliente.models import ArchivoMedia, Voucher
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            ev = Evento.objects.create(nombre="E3")
            p = Participante.objects.create(evento=ev, nombres="A", dni="9", cantidad=1, precio=1)
            v = Voucher.objects.create(participante=p, imagen=SimpleUploadedFile("v.png", self._png(), content_type="image/png"))
            self.assertTrue(ArchivoMedia.objects.filter(ruta=v.imagen.name).exists())

    def test_un_fallo_inesperado_de_whatsapp_se_informa_sin_error_500(self):
        from cliente.views import enviar_whatsapp_entrada
        ev = Evento.objects.create(nombre="E4", whatsapp_provider="CUSTOM_API", whatsapp_api_url="https://x.test")
        p = Participante.objects.create(evento=ev, nombres="A", dni="8", celular="955060412", cantidad=1, precio=1)
        with mock.patch("cliente.views._enviar_whatsapp_entrada", side_effect=RuntimeError("boom")):
            estado, detalle = enviar_whatsapp_entrada(p, None)
        self.assertEqual(estado, "error")
        self.assertIn("boom", detalle)


class EventoNoPierdeDatosTestCase(TestCase):
    """Editar el evento no debe borrar datos: caché, dos personas a la vez y campos ausentes."""

    def setUp(self):
        import re
        self.re = re
        self.user = User.objects.create_superuser("adm3", "a3@test.com", "pass12345")
        PerfilUsuario.objects.get_or_create(user=self.user, defaults={"rol": "SUPERADMIN"})
        self.client.login(username="adm3", password="pass12345")
        self.evento = Evento.objects.create(nombre="Despertar", aforo_maximo=1000)
        self.tarifa = Tarifa.objects.create(evento=self.evento, tipo_entrada="FULL ACCESS", puerta=100)
        self.url = reverse("evento_editar", kwargs={"pk": self.evento.pk})

    def _estado(self):
        html = self.client.get(self.url).content.decode()
        return self.re.search(r'name="_estado_evento" value="([0-9a-f]{40})"', html).group(1)

    def _datos(self, estado, **extra):
        d = {
            "_estado_evento": estado, "nombre": "Despertar", "descripcion": "", "aforo_maximo": "1000",
            "limite_entradas_persona": "5", "color_primario": "#7b1fa2",
            "tariff_id": [str(self.tarifa.pk)], "tariff_name": ["FULL ACCESS"], "tariff_p1": ["0"],
            "tariff_p2": ["0"], "tariff_p3": ["0"], "tariff_puerta": ["100"], "tariff_dias": ["1"],
            "tariff_hdesde": [""], "tariff_hhasta": [""],
        }
        d.update(extra)
        return d

    def test_guardar_y_reabrir_conserva_la_configuracion_de_whatsapp(self):
        cabecera = "X-API-Key: owa_k1_PRUEBA"
        self.client.post(self.url, self._datos(self._estado(), whatsapp_provider="CUSTOM_API",
                                               whatsapp_api_headers=cabecera, imgbb_api_key="k"))
        html = self.client.get(self.url).content.decode()
        self.assertIn("owa_k1_PRUEBA", html)
        self.assertRegex(html, r'value="CUSTOM_API"\s+selected')
        # un segundo guardado sin tocar nada tampoco la pierde
        self.client.post(self.url, self._datos(self._estado(), whatsapp_provider="CUSTOM_API",
                                               whatsapp_api_headers=cabecera, imgbb_api_key="k"))
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.whatsapp_api_headers, cabecera)

    def test_formulario_viejo_no_pisa_los_cambios_de_otra_persona(self):
        estado_viejo = self._estado()                       # pestaña/caché con el formulario antiguo
        Evento.objects.filter(pk=self.evento.pk).update(whatsapp_api_headers="X-API-Key: NUEVA")
        resp = self.client.post(self.url, self._datos(estado_viejo, whatsapp_api_headers="X-API-Key: VIEJA"),
                                follow=True)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.whatsapp_api_headers, "X-API-Key: NUEVA")
        self.assertTrue(any("cambió mientras lo editabas" in str(m) for m in resp.context["messages"]))

    def test_campos_ausentes_no_se_restablecen(self):
        Evento.objects.filter(pk=self.evento.pk).update(
            smtp_host="smtp.gmail.com", smtp_user="contacto@hilariogrp.com",
            default_from_email="Soporte <contacto@hilariogrp.com>")
        # el formulario no envía smtp_*; antes se restablecían a sendgrid / apikey
        self.client.post(self.url, self._datos(self._estado()))
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.smtp_host, "smtp.gmail.com")
        self.assertEqual(self.evento.smtp_user, "contacto@hilariogrp.com")
        self.assertEqual(self.evento.default_from_email, "Soporte <contacto@hilariogrp.com>")

    def test_el_formulario_no_se_guarda_en_cache_del_navegador(self):
        cc = self.client.get(self.url).headers.get("Cache-Control", "")
        self.assertIn("no-store", cc)
        self.assertIn("no-cache", cc)

    def test_el_formulario_muestra_los_mensajes_de_guardado(self):
        resp = self.client.post(self.url, self._datos(self._estado()), follow=True)
        self.assertEqual(resp.status_code, 200)
        # un guardado rechazado vuelve al editor y ahora el aviso se ve en pantalla
        resp = self.client.post(self.url, self._datos("0" * 40), follow=True)
        self.assertContains(resp, "cambió mientras lo editabas")


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
