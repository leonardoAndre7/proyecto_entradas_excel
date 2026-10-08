/**
 * Hoja de ventas EDE → Sistema de Entradas  (versión con separaciones, descuentos y cortesías)
 * ------------------------------------------------------------------------------------------
 * 1) crearFormularioVentas(): crea el formulario NUEVO de ventas y lo enlaza a esta hoja.
 * 2) Cada respuesta se envía sola al sistema (POST /api/registrar-participante/) y el resultado
 *    queda escrito en la columna SISTEMA de la fila.
 *
 * REGLAS QUE APLICA EL SISTEMA
 *  - El DNI identifica la entrada. Si la misma persona se registra otra vez con el mismo DNI, el pago
 *    se SUMA a su entrada (mismo ID). Al completar el total se envía la entrada sola; si falta, NO.
 *  - Un descuento (precio menor al de la tarifa) o una cortesía exige "Autorizado por".
 *
 * INSTALACIÓN (una sola vez)
 *  1. En la hoja: Extensiones → Apps Script. Pega todo este archivo (reemplaza lo anterior) y guarda.
 *  2. Propiedades de la secuencia de comandos (engranaje → Configuración del proyecto):
 *       API_URL   = https://ede-evento.com/api/registrar-participante/
 *       API_KEY   = (la clave de la hoja; la misma que está en API_KEYS_EXTRA de Render)
 *       EVENTO_ID = 4
 *  3. Activador (reloj): función alEnviarFormulario · De una hoja de cálculo · Al enviar el formulario.
 *     (Si ya lo tenías, no hay que repetirlo.)
 *  4. Ejecuta una vez la función crearFormularioVentas y acepta los permisos.
 */

var HOJA_ANTIGUA = 'VENTAS';           // respuestas del formulario anterior
var COLUMNA_ESTADO = 'SISTEMA';
var ENVIAR_AL_COMPLETAR = true;        // true: al completar el pago se envía la entrada sola
var ASESORES_FORM = ['Daniel', 'Irma Ramos', 'Rosa Espinoza', 'Yaneth Taquila'];

// Nombre de la tarifa en el sistema para cada texto del formulario (minúsculas y sin tildes)
var TIPOS = {
  'emprendedor': 'EMPRENDEDOR',
  'empresarial': 'EMPRESARIAL',
  'vip': 'VIP'
};

// Corrige variantes de escritura de los asesores (minúsculas y sin tildes → nombre correcto)
var ASESORES = {
  'daniel': 'Daniel',
  'irma ramos': 'Irma Ramos',
  'rosa espinoza': 'Rosa Espinoza',
  'yaneth taquila': 'Yaneth Taquila',
  'yaneth taquiloa': 'Yaneth Taquila'
};

var REGISTROS = {
  'pago completo': 'completo',
  'separacion (abono parcial)': 'separacion',
  'completar pago de una separacion': 'completar',
  'descuento autorizado': 'descuento',
  'cortesia (gratis)': 'cortesia'
};
var ETAPAS = {'preventa 1': 'pre1', 'preventa 2': 'pre2', 'preventa 3': 'pre3', 'puerta': 'puerta'};

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Sistema EDE')
    .addItem('Enviar filas pendientes', 'enviarPendientes')
    .addItem('Probar conexión', 'probarConexion')
    .addItem('Crear formulario nuevo de ventas', 'crearFormularioVentas')
    .addToUi();
}

/** Activador: se ejecuta solo cuando llega una respuesta nueva de cualquier formulario de esta hoja. */
function alEnviarFormulario(e) {
  var hoja = e.range.getSheet();
  if (hojasDeVentas_().indexOf(hoja.getName()) === -1) return;
  enviarFila_(hoja, e.range.getRow());
}

function hojasDeVentas_() {
  var nueva = PropertiesService.getScriptProperties().getProperty('HOJA_NUEVA');
  return nueva ? [HOJA_ANTIGUA, nueva] : [HOJA_ANTIGUA];
}

/** Envía todas las filas que aún no tienen "OK" (útil para reintentar o cargar las anteriores). */
function enviarPendientes() {
  var contar = {ok: 0, error: 0, omitidas: 0};
  hojasDeVentas_().forEach(function (nombre) {
    var hoja = SpreadsheetApp.getActive().getSheetByName(nombre);
    if (!hoja) return;
    for (var fila = 2; fila <= hoja.getLastRow(); fila++) {
      var r = enviarFila_(hoja, fila);
      if (r === 'ok') contar.ok++; else if (r === 'error') contar.error++; else contar.omitidas++;
    }
  });
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

// =============================== ENVÍO DE UNA FILA ===============================

function enviarFila_(hoja, fila) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var enc = encabezados_(hoja);
    var colEstado = columnaEstado_(hoja, enc);
    var estado = String(hoja.getRange(fila, colEstado).getValue() || '');
    if (/^(OK|YA EXISTE)/.test(estado)) return 'omitida';

    var v = function () { return leer_(hoja, fila, enc, Array.prototype.slice.call(arguments)); };
    var nombres = limpiar_(v('nombres y apellidos'));
    if (!nombres) return 'omitida';

    var props = PropertiesService.getScriptProperties();
    var nuevoFormulario = !!enc['monto pagado ahora (s/)'];
    var tipoOriginal = limpiar_(v('tipo de entrada'));
    var asesor = limpiar_(v('asesor'));
    var dni = limpiar_(v('dni', 'numero de dni'));
    var marca = v('marca temporal');

    var cuerpo = {
      evento_id: Number(props.getProperty('EVENTO_ID')),
      estricto: true,                          // si la tarifa no existe en el sistema, avisa y no crea
      nombres: nombres,
      dni: dni,
      celular: String(v('celular', 'numero de celular') || '').replace(/\D/g, ''),
      correo: limpiar_(v('correo electronico')),
      tipo_entrada: TIPOS[sinTildes_(tipoOriginal)] || tipoOriginal,
      vendedor: ASESORES[sinTildes_(asesor)] || asesor,
      metodo_pago: limpiar_(v('metodo de pago')),
      voucher_url: primerEnlace_(v('voucher de pago')),
      referencia: referencia_(marca, dni, fila)
    };

    if (nuevoFormulario) {
      var registro = REGISTROS[sinTildes_(v('tipo de registro'))] || '';
      cuerpo.tipo_registro = registro;
      cuerpo.tipo_tarifa = ETAPAS[sinTildes_(v('etapa de precio'))] || 'pre1';
      cuerpo.monto_pagado = registro === 'cortesia' ? 0 : (numero_(v('monto pagado ahora (s/)')) || 0);
      var acordado = numero_(v('precio acordado final (s/)'));
      if (acordado !== null && registro === 'descuento') cuerpo.precio_final = acordado;
      cuerpo.autorizado_por = limpiar_(v('autorizado por'));
      cuerpo.notas = [limpiar_(v('motivo del descuento o cortesia')), limpiar_(v('observaciones'))]
                       .filter(String).join(' | ');
      cuerpo.enviar_entrada = ENVIAR_AL_COMPLETAR;    // el sistema solo la envía si el pago queda completo
    } else {
      // Formulario anterior: se mantiene como antes (todo llega como pago por confirmar)
      cuerpo.precio_final = numero_(v('precio de entrada'));
      cuerpo.notas = [limpiar_(v('detalle')), limpiar_(v('observacion'))].filter(String).join(' | ');
      cuerpo.pago_confirmado = false;
    }

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
      if (nuevoFormulario) {
        var detalle = datos.completo ? 'COMPLETO' : 'FALTA S/ ' + datos.saldo;
        celdaEstado.setValue((datos.duplicado ? 'YA EXISTE #' : 'OK #') + datos.id + ' (' + datos.cod_cliente + ') · ' +
                             detalle + (datos.entrada_enviada ? ' · entrada enviada' : ''));
      } else {
        celdaEstado.setValue((datos.duplicado ? 'YA EXISTE #' : 'OK #') + datos.id);
      }
      return 'ok';
    }
    if (codigo === 409 && !nuevoFormulario) {      // formulario anterior: mismo DNI ya registrado
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

// =============================== FORMULARIO NUEVO ===============================

/**
 * Crea el formulario nuevo de ventas (el anterior queda intacto) y lo enlaza a esta hoja.
 * Apps Script no puede crear la pregunta de "subir archivo": agrégala a mano (ver aviso final).
 */
function crearFormularioVentas() {
  var form = FormApp.create('Registro de ventas · El Despertar del Emprendedor 2026');
  form.setDescription('Registra aquí cada venta. Si el cliente PAGA POR PARTES, vuelve a registrarlo con el MISMO DNI ' +
                      'y elige "Completar pago de una separación": el sistema suma el pago a su misma entrada. ' +
                      'Cualquier descuento o cortesía necesita decir quién lo autorizó.');
  form.setAllowResponseEdits(false);
  form.setCollectEmail(false);
  form.setProgressBar(true);

  // ---------- Página 1: cliente, entrada y tipo de registro ----------
  form.addSectionHeaderItem().setTitle('1. Datos del cliente');
  form.addTextItem().setTitle('Nombres y apellidos').setRequired(true);
  form.addTextItem().setTitle('DNI').setRequired(true)
      .setHelpText('Solo números (8 a 12). Es el identificador de la entrada: no lo escribas mal.')
      .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^[0-9]{8,12}$')
                       .setHelpText('Escribe solo números, sin espacios ni puntos.').build());
  form.addTextItem().setTitle('Celular').setRequired(true)
      .setHelpText('9 dígitos. Aquí le llegará su entrada por WhatsApp.')
      .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^9[0-9]{8}$')
                       .setHelpText('Debe tener 9 dígitos y empezar con 9.').build());
  form.addTextItem().setTitle('Correo electrónico').setRequired(true)
      .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());

  form.addSectionHeaderItem().setTitle('2. Entrada');
  form.addListItem().setTitle('Tipo de entrada').setRequired(true).setChoiceValues(['Emprendedor', 'Empresarial', 'VIP']);
  form.addListItem().setTitle('Etapa de precio').setRequired(true)
      .setHelpText('El sistema toma de aquí el precio de lista de la entrada.')
      .setChoiceValues(['Preventa 1', 'Preventa 2', 'Preventa 3', 'Puerta']);
  form.addListItem().setTitle('Asesor').setRequired(true).setChoiceValues(ASESORES_FORM);

  form.addSectionHeaderItem().setTitle('3. ¿Qué vas a registrar?');
  var tipoReg = form.addMultipleChoiceItem().setTitle('Tipo de registro').setRequired(true);

  // ---------- Página de descuento ----------
  var pDesc = form.addPageBreakItem().setTitle('Descuento autorizado')
      .setHelpText('Un descuento solo se registra si alguien lo autorizó.');
  form.addTextItem().setTitle('Precio acordado final (S/)').setRequired(true)
      .setHelpText('Lo que cuesta la entrada CON el descuento (no lo que paga ahora).')
      .setValidation(FormApp.createTextValidation().requireNumber().build());
  form.addTextItem().setTitle('Autorizado por').setRequired(true)
      .setHelpText('Nombre de quien autorizó el descuento.');
  form.addParagraphTextItem().setTitle('Motivo del descuento o cortesia').setRequired(true);

  // ---------- Página de cortesía ----------
  var pCort = form.addPageBreakItem().setTitle('Cortesía (gratis)')
      .setHelpText('La entrada se registra sin costo. Se envía sola al registrarse.');
  form.addTextItem().setTitle('Autorizado por').setRequired(true);
  form.addParagraphTextItem().setTitle('Motivo del descuento o cortesia').setRequired(true);

  // ---------- Página de pago ----------
  var pPago = form.addPageBreakItem().setTitle('Pago');
  form.addListItem().setTitle('Método de pago').setRequired(true)
      .setChoiceValues(['Yape', 'Plin', 'Transferencia bancaria', 'Tarjeta de crédito o débito',
                        'Pagape', 'Efectivo', 'Yape y transferencia']);
  form.addTextItem().setTitle('Monto pagado ahora (S/)').setRequired(true)
      .setHelpText('SOLO lo que el cliente paga en este momento. Si es una separación, el abono.')
      .setValidation(FormApp.createTextValidation().requireNumber().build());
  form.addParagraphTextItem().setTitle('Observaciones')
      .setHelpText('Opcional. Ej.: número de operación.');

  // ---------- Navegación según el tipo de registro ----------
  pDesc.setGoToPage(pPago);
  pCort.setGoToPage(FormApp.PageNavigationType.SUBMIT);
  tipoReg.setChoices([
    tipoReg.createChoice('Pago completo', pPago),
    tipoReg.createChoice('Separación (abono parcial)', pPago),
    tipoReg.createChoice('Completar pago de una separación', pPago),
    tipoReg.createChoice('Descuento autorizado', pDesc),
    tipoReg.createChoice('Cortesía (gratis)', pCort)
  ]);

  // ---------- Enlazar a esta hoja y registrar la pestaña de respuestas ----------
  var libro = SpreadsheetApp.getActive();
  form.setDestination(FormApp.DestinationType.SPREADSHEET, libro.getId());
  SpreadsheetApp.flush();
  var nombreHoja = '';
  libro.getSheets().forEach(function (s) {
    var url = s.getFormUrl();
    if (url && FormApp.openByUrl(url).getId() === form.getId()) {
      s.setName('VENTAS 2026');
      nombreHoja = 'VENTAS 2026';
    }
  });
  if (nombreHoja) PropertiesService.getScriptProperties().setProperty('HOJA_NUEVA', nombreHoja);

  SpreadsheetApp.getUi().alert(
    'Formulario creado ✔\n\n' +
    'ENLACE PARA EL PERSONAL:\n' + form.getPublishedUrl() + '\n\n' +
    'EDITARLO:\n' + form.getEditUrl() + '\n\n' +
    'FALTA UN PASO MANUAL: en el formulario, en la página "Pago", agrega una pregunta de tipo ' +
    '"Subir archivo" llamada exactamente  Voucher de pago  (Apps Script no puede crearla).\n\n' +
    (nombreHoja ? 'Las respuestas llegarán a la pestaña "' + nombreHoja + '".' :
                  'Si la pestaña de respuestas no se renombró sola, créala desde el formulario (Respuestas → Vincular a hojas).'));
}

// =============================== AUXILIARES ===============================

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

/** Lee la primera columna que exista de la lista de nombres alternativos. */
function leer_(hoja, fila, enc, nombres) {
  for (var i = 0; i < nombres.length; i++) {
    var col = enc[nombres[i]];
    if (col) return hoja.getRange(fila, col).getValue();
  }
  return '';
}

function limpiar_(t) { return String(t === null || t === undefined ? '' : t).replace(/\s+/g, ' ').trim(); }

function sinTildes_(t) {
  return limpiar_(t).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

function numero_(t) {
  if (t === '' || t === null || t === undefined) return null;
  var n = parseFloat(String(t).replace(/[^\d.,-]/g, '').replace(/,(?=\d{3}(\D|$))/g, '').replace(',', '.'));
  return isNaN(n) ? null : n;
}

function primerEnlace_(t) {
  var m = String(t || '').match(/https?:\/\/[^\s,]+/);
  return m ? m[0] : '';
}

/** Identificador estable de la fila: reintentar el envío no suma el mismo pago dos veces. */
function referencia_(marca, dni, fila) {
  var sello = (marca instanceof Date)
      ? Utilities.formatDate(marca, 'GMT', 'yyyyMMddHHmmss') : 'fila' + fila;
  return sello + '-' + (dni || 'sin-dni');
}
