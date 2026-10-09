import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from cliente.models import Evento, Tarifa, PerfilUsuario, Participante, CodigoPuerta

# Evita depender del manifest de collectstatic al renderizar {% static %}
SIN_MANIFEST = override_settings(
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)


def _t(dia, hora=10):
    return timezone.make_aware(datetime.datetime(2026, 11, dia, hora, 0), timezone.get_current_timezone())


@SIN_MANIFEST
class PuertaBase(TestCase):
    def setUp(self):
        cache.clear()
        self.evento = Evento.objects.create(nombre="EDE", fecha_evento=datetime.date(2026, 11, 14))
        self.otro = Evento.objects.create(nombre="Otro")
        d1, d2 = datetime.date(2026, 11, 14), datetime.date(2026, 11, 15)
        self.emp = Tarifa.objects.create(evento=self.evento, tipo_entrada="EMPRESARIAL", dias_validos=2,
                                         fecha_desde=d1, fecha_hasta=d2)
        self.emprendedor = Tarifa.objects.create(evento=self.evento, tipo_entrada="EMPRENDEDOR", dias_validos=1,
                                                 fecha_desde=d1, fecha_hasta=d1,
                                                 hora_desde=datetime.time(8, 0), hora_hasta=datetime.time(20, 0))
        self.codigo_obj, self.codigo = CodigoPuerta.generar(self.evento, "Puerta 1", _t(16))
        self.c = Client()

    def part(self, tarifa=None, dni="1", evento=None, **kw):
        return Participante.objects.create(evento=evento or self.evento, tarifa=tarifa or self.emp, nombres="Ana",
                                           apellidos="Pérez Soto", dni=dni, correo="a@b.com", cantidad=1, **({"precio": 1} | kw))

    def token(self, codigo=None):
        with mock.patch("cliente.models.ahora_actual", return_value=_t(14)):
            r = self.c.post(reverse("puerta_acceso"), {"codigo": codigo or self.codigo}, content_type="application/json")
        return r.json().get("token")

    def escanear(self, qr, momento, token=None):
        tok = token or self.token()
        with mock.patch("cliente.models.ahora_actual", return_value=momento):
            return self.c.post(reverse("puerta_validar"), {"qr": qr}, content_type="application/json",
                               HTTP_X_PUERTA_TOKEN=tok)


class AccesoTests(PuertaBase):
    def test_codigo_correcto(self):
        r = self.c.post(reverse("puerta_acceso"), {"codigo": self.codigo}, content_type="application/json")
        self.assertTrue(r.json()["ok"])
        self.assertIn("token", r.json())

    def test_codigo_acepta_minusculas_y_sin_guion(self):
        r = self.c.post(reverse("puerta_acceso"), {"codigo": self.codigo.lower().replace("-", "")},
                        content_type="application/json")
        self.assertTrue(r.json()["ok"])

    def test_codigo_incorrecto(self):
        r = self.c.post(reverse("puerta_acceso"), {"codigo": "AAAA-BBBB"}, content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_codigo_revocado(self):
        CodigoPuerta.objects.update(activo=False)
        r = self.c.post(reverse("puerta_acceso"), {"codigo": self.codigo}, content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_codigo_vencido(self):
        CodigoPuerta.objects.update(vence_en=timezone.now() - datetime.timedelta(minutes=1))
        r = self.c.post(reverse("puerta_acceso"), {"codigo": self.codigo}, content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("venci", r.json()["error"])

    def test_bloqueo_por_intentos(self):
        for _ in range(8):
            self.c.post(reverse("puerta_acceso"), {"codigo": "ZZZZ-ZZZZ"}, content_type="application/json")
        r = self.c.post(reverse("puerta_acceso"), {"codigo": self.codigo}, content_type="application/json")
        self.assertEqual(r.status_code, 429)

    def test_el_codigo_no_se_guarda_en_claro(self):
        self.assertNotIn(self.codigo.replace("-", ""), self.codigo_obj.codigo_hash)
        self.assertEqual(len(self.codigo_obj.codigo_hash), 64)

    def test_vencimiento_por_defecto_cubre_dia_2(self):
        v = CodigoPuerta.vencimiento_por_defecto(self.evento)
        self.assertGreater(v, _t(15, 23))


class ValidarTests(PuertaBase):
    def test_sin_token_rechaza(self):
        r = self.c.post(reverse("puerta_validar"), {"qr": "x"}, content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_token_falso_rechaza(self):
        r = self.c.post(reverse("puerta_validar"), {"qr": "x"}, content_type="application/json",
                        HTTP_X_PUERTA_TOKEN="inventado")
        self.assertEqual(r.status_code, 401)

    def test_revocado_corta_sesion_ya_iniciada(self):
        p = self.part()
        tok = self.token()
        CodigoPuerta.objects.update(activo=False)
        r = self.escanear(p.token, _t(14), token=tok)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["motivo"], "revocado")

    def test_vencido_corta_sesion_ya_iniciada(self):
        p = self.part()
        tok = self.token()
        r = self.escanear(p.token, _t(20), token=tok)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["motivo"], "vencido")

    def test_valido_dia1_y_dia2_empresarial(self):
        p = self.part()
        tok = self.token()
        self.assertTrue(self.escanear(p.token, _t(14), tok).json()["valido"])
        self.assertTrue(self.escanear(p.token, _t(15), tok).json()["valido"])
        self.assertEqual(p.ingresos.count(), 2)

    def test_duplicado_mismo_dia(self):
        p = self.part()
        tok = self.token()
        self.escanear(p.token, _t(14, 10), tok)
        d = self.escanear(p.token, _t(14, 12), tok).json()
        self.assertFalse(d["valido"])
        self.assertEqual(d["motivo"], "duplicado")

    def test_tarifa_un_dia_segunda_vez_rechaza(self):
        p = self.part(tarifa=self.emprendedor)
        tok = self.token()
        self.assertTrue(self.escanear(p.token, _t(14, 10), tok).json()["valido"])
        self.assertFalse(self.escanear(p.token, _t(14, 11), tok).json()["valido"])

    def test_dia_fuera_de_rango(self):
        p = self.part(tarifa=self.emprendedor)
        d = self.escanear(p.token, _t(15)).json()
        self.assertFalse(d["valido"])
        self.assertEqual(d["motivo"], "fuera_de_fecha")

    def test_fuera_de_horario(self):
        p = self.part(tarifa=self.emprendedor)
        d = self.escanear(p.token, _t(14, 22)).json()
        self.assertEqual(d["motivo"], "fuera_de_horario")

    def test_saldo_pendiente(self):
        p = self.part(precio=100)
        p.pagos.create(monto=40)
        Participante.objects.filter(pk=p.pk).update(monto_pagado=40)
        p.refresh_from_db()
        d = self.escanear(p.token, _t(14)).json()
        self.assertFalse(d["valido"])
        self.assertEqual(d["motivo"], "saldo_pendiente")
        self.assertEqual(p.ingresos.count(), 0)

    def test_entrada_de_otro_evento(self):
        t = Tarifa.objects.create(evento=self.otro, tipo_entrada="VIP")
        p = self.part(tarifa=t, evento=self.otro, dni="9")
        d = self.escanear(p.token, _t(14)).json()
        self.assertEqual(d["motivo"], "otro_evento")
        self.assertEqual(p.ingresos.count(), 0)
        self.assertNotIn("nombre", d)

    def test_qr_desconocido(self):
        d = self.escanear("no-existe", _t(14)).json()
        self.assertEqual(d["motivo"], "no_encontrado")

    def test_acepta_url_completa_del_qr(self):
        p = self.part()
        d = self.escanear(f"https://ede-evento.com/participantes/validar/{p.token}/", _t(14)).json()
        self.assertTrue(d["valido"])

    def test_no_expone_datos_personales(self):
        p = self.part(dni="12345678")
        crudo = self.escanear(p.token, _t(14)).content.decode()
        self.assertNotIn("12345678", crudo)
        self.assertNotIn("a@b.com", crudo)
        self.assertNotIn("Soto", crudo)
        self.assertIn("Ana P.", crudo)

    def test_cuenta_escaneos_y_ultimo_uso(self):
        p = self.part()
        self.escanear(p.token, _t(14))
        self.codigo_obj.refresh_from_db()
        self.assertEqual(self.codigo_obj.escaneos, 1)
        self.assertIsNotNone(self.codigo_obj.ultimo_uso)

    def test_respuestas_sin_cache(self):
        r = self.c.post(reverse("puerta_validar"), {"qr": "x"}, content_type="application/json")
        self.assertIn("no-store", r["Cache-Control"])


class RegresionLoginTests(PuertaBase):
    def test_escaneo_con_login_sigue_igual(self):
        user = User.objects.create_user("admin", password="x")
        PerfilUsuario.objects.create(user=user, rol="SUPERADMIN")
        self.c.login(username="admin", password="x")
        p = self.part()
        with mock.patch("cliente.models.ahora_actual", return_value=_t(14)):
            r = self.c.get(reverse("validar_entrada", args=[p.token]))
        self.assertTemplateUsed(r, "cliente/entrada_valida.html")
        with mock.patch("cliente.models.ahora_actual", return_value=_t(14, 12)):
            r = self.c.get(reverse("validar_entrada", args=[p.token]))
        self.assertTemplateUsed(r, "cliente/entrada_usada.html")

    def test_validar_con_login_sin_sesion_pide_login(self):
        p = self.part()
        r = Client().get(reverse("validar_entrada", args=[p.token]))
        self.assertEqual(r.status_code, 302)


class PaginasYPanelTests(PuertaBase):
    def test_app_manifest_y_sw(self):
        self.assertEqual(self.c.get(reverse("puerta_app")).status_code, 200)
        self.assertEqual(self.c.get(reverse("puerta_manifest")).json()["display"], "standalone")
        self.assertEqual(self.c.get(reverse("puerta_sw"))["Service-Worker-Allowed"], "/puerta/")

    def test_panel_exige_login_y_superadmin(self):
        self.assertEqual(self.c.get(reverse("puerta_panel")).status_code, 302)
        u = User.objects.create_user("reg", password="x")
        PerfilUsuario.objects.create(user=u, rol="REGISTRADOR")
        self.c.login(username="reg", password="x")
        r = self.c.post(reverse("puerta_panel"), {"accion": "crear", "evento": self.evento.id, "nombre": "X"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CodigoPuerta.objects.count(), 1)

    def test_superadmin_crea_y_revoca(self):
        u = User.objects.create_user("sa", password="x")
        PerfilUsuario.objects.create(user=u, rol="SUPERADMIN")
        self.c.login(username="sa", password="x")
        r = self.c.post(reverse("puerta_panel"), {"accion": "crear", "evento": self.evento.id, "nombre": "Puerta 2"})
        self.assertContains(r, "Puerta 2")
        nuevo = CodigoPuerta.objects.get(nombre="Puerta 2")
        self.assertGreater(nuevo.vence_en, _t(15, 23))
        self.c.post(reverse("puerta_panel"), {"accion": "revocar", "id": nuevo.id})
        nuevo.refresh_from_db()
        self.assertFalse(nuevo.activo)


class IpYTokenTests(PuertaBase):
    def test_xff_falsificado_no_evade_el_limite(self):
        for i in range(8):
            self.c.post(reverse("puerta_acceso"), {"codigo": "ZZZZ-ZZZZ"}, content_type="application/json",
                        HTTP_X_FORWARDED_FOR=f"1.1.1.{i}, 9.9.9.9")
        r = self.c.post(reverse("puerta_acceso"), {"codigo": self.codigo}, content_type="application/json",
                        HTTP_X_FORWARDED_FOR="2.2.2.2, 9.9.9.9")
        self.assertEqual(r.status_code, 429)

    def test_panel_sin_cache(self):
        u = User.objects.create_user("sa2", password="x")
        PerfilUsuario.objects.create(user=u, rol="SUPERADMIN")
        self.c.login(username="sa2", password="x")
        self.assertIn("no-store", self.c.get(reverse("puerta_panel"))["Cache-Control"])


class RobustezTests(PuertaBase):
    def test_cuerpo_json_que_no_es_objeto_no_da_500(self):
        tok = self.token()
        for cuerpo in ("[]", "null", "5", '"x"'):
            r = self.c.post(reverse("puerta_validar"), cuerpo, content_type="application/json", HTTP_X_PUERTA_TOKEN=tok)
            self.assertEqual(r.status_code, 200, cuerpo)
        r = self.c.post(reverse("puerta_acceso"), "[]", content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_qr_con_query_y_mayusculas(self):
        p = self.part()
        d = self.escanear(f"https://ede-evento.com/participantes/validar/{p.token.upper()}/?x=1#f", _t(14)).json()
        self.assertTrue(d["valido"])
