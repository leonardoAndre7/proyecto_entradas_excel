/**
 * Hoja de ventas EDE → Sistema de Entradas
 * ----------------------------------------
 * Envía cada venta de la hoja "VENTAS" (respuestas del Google Forms) a la API del sistema
 * (POST /api/registrar-participante/). Anota el resultado en la columna SISTEMA de cada fila.
 *
 * INSTALACIÓN (una sola vez)
 *  1. En la hoja: Extensiones → Apps Script. Pega todo este archivo y guarda.
 *  2. Engranaje "Configuración del proyecto" → "Propiedades de la secuencia de comandos" → agrega:
 *       API_URL   = https://ede-evento.com/api/registrar-participante/
 *       API_KEY   = (la clave de la API; la misma que la variable API_KEY de Render)
 *       EVENTO_ID = 4
 *  3. Reloj "Activadores" → Añadir activador:
 *       función: alEnviarFormulario · origen: De una hoja de cálculo · tipo: Al enviar el formulario
 *  4. Vuelve a la hoja, recarga la página: aparece el menú "Sistema EDE".
 *     Prueba con "Probar conexión" y luego "Enviar filas pendientes".
 *
 * La clave NO se escribe en este código: queda en las propiedades del script.
 */

var HOJA = 'VENTAS';
var COLUMNA_ESTADO = 'SISTEMA';

// Nombre de la tarifa en el sistema para cada texto del formulario (en minúsculas y sin tildes)
var TIPOS = {
  'emprendedor': 'EMPRENDEDOR',
  'empresarial': 'EMPRESARIAL',
  'vip': 'VIP'
};

// Corrige variantes de escritura de los asesores (en minúsculas y sin tildes → nombre correcto)
var ASESORES = {
  'daniel': 'Daniel',
  'irma ramos': 'Irma Ramos',
  'rosa espinoza': 'Rosa Espinoza',
  'yaneth taquila': 'Yaneth Taquila',
  'yaneth taquiloa': 'Yaneth Taquila'
};

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Sistema EDE')
    .addItem('Enviar filas pendientes', 'enviarPendientes')
    .addItem('Probar conexión', 'probarConexion')
    .addToUi();
}

/** Activador: se ejecuta solo cuando llega una respuesta nueva del formulario. */
function alEnviarFormulario(e) {
  var hoja = e.range.getSheet();
  if (hoja.getName() !== HOJA) return;
  enviarFila_(hoja, e.range.getRow());
}

/** Envía todas las filas que aún no tienen "OK" (útil para reintentar o cargar las anteriores). */
function enviarPendientes() {
  var hoja = SpreadsheetApp.getActive().getSheetByName(HOJA);
  var ultima = hoja.getLastRow();
  var contar = {ok: 0, error: 0, omitidas: 0};
  for (var fila = 2; fila <= ultima; fila++) {
    var r = enviarFila_(hoja, fila);
    if (r === 'ok') contar.ok++; else if (r === 'error') contar.error++; else contar.omitidas++;
  }
  SpreadsheetApp.getUi().alert('Listo.\nEnviadas: ' + contar.ok + '\nCon error: ' + contar.error +
                               '\nOmitidas (vacías o ya enviadas): ' + contar.omitidas);
}

function probarConexion() {
  var p = PropertiesService.getScriptProperties();
  var resp = UrlFetchApp.fetch(p.getProperty('API_URL'), {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: {'X-API-Key': p.getProperty('API_KEY') || ''},
    payload: JSON.stringify({evento_id: Number(p.getProperty('EVENTO_ID')), nombres: ''})
  });
  var codigo = resp.getResponseCode();
  // Sin nombre el sistema responde 400: eso confirma que la clave y la dirección son correctas
  var mensaje = codigo === 400 ? 'Conexión correcta ✔ (la clave es válida)'
              : codigo === 403 ? 'La clave API_KEY es incorrecta'
              : codigo === 503 ? 'El servidor aún no tiene configurada la variable API_KEY'
              : 'Respuesta inesperada ' + codigo + ': ' + resp.getContentText().slice(0, 200);
  SpreadsheetApp.getUi().alert(mensaje);
}

// ---------------------------------------------------------------------------------------------

function enviarFila_(hoja, fila) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var enc = encabezados_(hoja);
    var colEstado = columnaEstado_(hoja, enc);
    var estado = String(hoja.getRange(fila, colEstado).getValue() || '');
    if (/^(OK|YA EXISTE)/.test(estado)) return 'omitida';

    var v = function (nombre) { return leer_(hoja, fila, enc, nombre); };
    var nombres = limpiar_(v('nombres y apellidos'));
    if (!nombres) return 'omitida';

    var tipoOriginal = limpiar_(v('tipo de entrada'));
    var tipo = TIPOS[sinTildes_(tipoOriginal)] || tipoOriginal;
    var asesor = limpiar_(v('asesor'));
    asesor = ASESORES[sinTildes_(asesor)] || asesor;
    var marca = v('marca temporal');
    var dni = limpiar_(v('numero de dni'));

    var detalle = [limpiar_(v('detalle')), limpiar_(v('observacion'))].filter(String).join(' | ');
    var props = PropertiesService.getScriptProperties();
    var cuerpo = {
      evento_id: Number(props.getProperty('EVENTO_ID')),
      estricto: true,                         // si la tarifa no existe en el sistema, avisa y no crea
      nombres: nombres,
      dni: dni,
      celular: String(v('numero de celular') || '').replace(/\D/g, ''),
      correo: limpiar_(v('correo electronico')),
      tipo_entrada: tipo,
      precio_final: numero_(v('precio de entrada')),
      vendedor: asesor,
      metodo_pago: limpiar_(v('metodo de pago')),
      voucher_url: primerEnlace_(v('voucher de pago')),
      notas: detalle,
      pago_confirmado: false,                 // contabilidad lo confirma dentro del sistema
      referencia: referencia_(marca, dni, fila)
    };

    var resp = UrlFetchApp.fetch(props.getProperty('API_URL'), {
      method: 'post', contentType: 'application/json', muteHttpExceptions: true,
      headers: {'X-API-Key': props.getProperty('API_KEY') || ''},
      payload: JSON.stringify(cuerpo)
    });
    var codigo = resp.getResponseCode();
    var datos = {};
    try { datos = JSON.parse(resp.getContentText()); } catch (err) {}

    var celdaEstado = hoja.getRange(fila, colEstado);
    if (codigo === 200 && datos.ok) {
      celdaEstado.setValue((datos.duplicado ? 'YA EXISTE #' : 'OK #') + datos.id);
      return 'ok';
    }
    if (codigo === 409) {                      // mismo DNI ya registrado en el evento
      celdaEstado.setValue('YA EXISTE (DNI repetido)');
      return 'ok';
    }
    var extra = datos.tarifas_disponibles ? ' Tarifas: ' + datos.tarifas_disponibles.join(', ') : '';
    celdaEstado.setValue('ERROR ' + codigo + ': ' + (datos.error || resp.getContentText().slice(0, 150)) + extra);
    return 'error';
  } finally {
    lock.releaseLock();
  }
}

function encabezados_(hoja) {
  var fila1 = hoja.getRange(1, 1, 1, hoja.getLastColumn()).getValues()[0];
  var mapa = {};
  fila1.forEach(function (t, i) { mapa[sinTildes_(limpiar_(t))] = i + 1; });
  return mapa;
}

function columnaEstado_(hoja, enc) {
  var col = enc[sinTildes_(COLUMNA_ESTADO)];
  if (!col) {
    col = hoja.getLastColumn() + 1;
    hoja.getRange(1, col).setValue(COLUMNA_ESTADO);
    enc[sinTildes_(COLUMNA_ESTADO)] = col;
  }
  return col;
}

function leer_(hoja, fila, enc, nombre) {
  var col = enc[nombre];
  return col ? hoja.getRange(fila, col).getValue() : '';
}

function limpiar_(t) { return String(t === null || t === undefined ? '' : t).replace(/\s+/g, ' ').trim(); }

function sinTildes_(t) {
  return limpiar_(t).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

function numero_(t) {
  var n = parseFloat(String(t).replace(/[^\d.,-]/g, '').replace(/,(?=\d{3}(\D|$))/g, '').replace(',', '.'));
  return isNaN(n) ? null : n;
}

function primerEnlace_(t) {
  var m = String(t || '').match(/https?:\/\/[^\s,]+/);
  return m ? m[0] : '';
}

/** Identificador estable de la venta: reintentar la misma fila no crea un participante repetido. */
function referencia_(marca, dni, fila) {
  var sello = (marca instanceof Date)
      ? Utilities.formatDate(marca, 'GMT', 'yyyyMMddHHmmss') : 'fila' + fila;
  return sello + '-' + (dni || 'sin-dni');
}
