/**
 * Hoja de ventas EDE → Sistema de Entradas  (separaciones, descuentos y cortesías)
 * --------------------------------------------------------------------------------
 * 1) modificarFormularioExistente(): AGREGA al formulario que ya usas las preguntas nuevas y lo
 *    ordena en páginas. No borra ni renombra ninguna pregunta ni toca las respuestas anteriores.
 * 2) Cada respuesta nueva se envía sola al sistema (POST /api/registrar-participante/) y el
 *    resultado queda escrito en la columna SISTEMA de la fila.
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
 *  4. Elige la función  revisarFormulario  y ejecútala (solo lee, no cambia nada): confirma que
 *     encuentra todas las preguntas. Luego ejecuta  modificarFormularioExistente.
 */

var FORM_ID = '1Co_DVlEM-7uDVq8bptmjXAuXcEPlq9ahbAkSZjfPvng';   // el formulario "EDE 2.0"
// ---- CONFIGURACIÓN (se edita aquí mismo; ya no hace falta "Propiedades de la secuencia") ----
var API_URL = 'https://ede-evento.com/api/registrar-participante/';
var API_KEY = 'PEGA_AQUI_LA_CLAVE';    // la misma que está en API_KEYS_EXTRA de Render
var EVENTO_ID = 4;
var HOJA = 'VENTAS';                   // pestaña donde llegan sus respuestas
var COLUMNA_ESTADO = 'SISTEMA';
var ENVIAR_AL_COMPLETAR = true;        // true: al completar el pago se envía la entrada sola

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
// Etapa que se usa cuando el formulario NO tiene la pregunta "Etapa de precio" (venta única):
// 'pre1' = Preventa 1, 'pre2', 'pre3' o 'puerta'
var ETAPA_UNICA = 'pre1';
var ETAPAS = {'preventa 1': 'pre1', 'preventa 2': 'pre2', 'preventa 3': 'pre3', 'puerta': 'puerta'};

// Preguntas que YA existen en el formulario (se buscan por su título, sin tildes ni mayúsculas)
var EXISTENTES = {
  nombres: 'nombres y apellidos',
  dni: 'numero de dni',
  celular: 'numero de celular',
  correo: 'correo electronico',
  metodo: 'metodo de pago',
  tipo: 'tipo de entrada',
  monto: 'precio de entrada',          // pasa a significar: lo que el cliente paga AHORA
  asesor: 'asesor',
  voucher: 'voucher de pago'
};

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Sistema EDE')
    .addItem('Enviar filas pendientes', 'enviarPendientes')
    .addItem('Probar conexión', 'probarConexion')
    .addItem('Revisar formulario (solo lee)', 'revisarFormulario')
    .addItem('Modificar formulario existente', 'modificarFormularioExistente')
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
  var contar = {ok: 0, error: 0, ya: 0, vacia: 0};
  var hoja = SpreadsheetApp.getActive().getSheetByName(HOJA);
  for (var fila = 2; fila <= hoja.getLastRow(); fila++) {
    var r = enviarFila_(hoja, fila);
    if (contar[r] !== undefined) contar[r]++;
  }
  SpreadsheetApp.getUi().alert('Listo.\nEnviadas: ' + contar.ok + '\nCon error: ' + contar.error +
                               '\nYa estaban enviadas (SISTEMA dice OK o YA EXISTE): ' + contar.ya +
                               '\nFilas sin nombre (vacías): ' + contar.vacia);
}

function probarConexion() {
  var resp = UrlFetchApp.fetch(API_URL, {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: {'X-API-Key': API_KEY},
    payload: JSON.stringify({evento_id: EVENTO_ID, nombres: ''})
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
    if (/^(OK|YA EXISTE)/.test(estado)) return 'ya';

    var v = function () { return leer_(hoja, fila, enc, Array.prototype.slice.call(arguments)); };
    var nombres = limpiar_(v('nombres y apellidos'));
    if (!nombres) return 'vacia';

    var tipoOriginal = limpiar_(v('tipo de entrada'));
    var asesor = limpiar_(v('asesor'));
    var dni = limpiar_(v('dni', 'numero de dni')).replace(/s+/g, '');
    var marca = v('marca temporal');
    // Sin "Tipo de registro" (filas del formulario anterior) se trata como pago normal: el sistema compara
    // lo pagado con el precio de la tarifa. Si cubre el precio, confirma el pago y envía la entrada solo;
    // si es menos, queda como separación (con saldo) y NO se envía hasta completarse.
    var registro = REGISTROS[sinTildes_(v('tipo de registro'))] || 'completo';

    var cuerpo = {
      evento_id: EVENTO_ID,
      estricto: true,                          // si la tarifa no existe en el sistema, avisa y no crea
      nombres: nombres,
      dni: dni,
      celular: String(v('celular', 'numero de celular') || '').replace(/\D/g, ''),
      correo: correo_(v('correo electronico')),
      tipo_entrada: TIPOS[sinTildes_(tipoOriginal)] || tipoOriginal,
      vendedor: ASESORES[sinTildes_(asesor)] || asesor,
      metodo_pago: limpiar_(v('metodo de pago')),
      voucher_url: primerEnlace_(v('voucher de pago')),
      referencia: referencia_(marca, dni, fila)
    };

    var nuevo = !!registro;
    if (nuevo) {
      cuerpo.tipo_registro = registro;
      cuerpo.tipo_tarifa = ETAPAS[sinTildes_(v('etapa de precio'))] || ETAPA_UNICA;
      // "Precio de Entrada" del formulario ahora es lo que el cliente paga en este momento
      cuerpo.monto_pagado = registro === 'cortesia' ? 0 : (numero_(v('precio de entrada')) || 0);
      var acordado = numero_(v('precio acordado final (s/)'));
      if (acordado !== null && registro === 'descuento') cuerpo.precio_final = acordado;
      cuerpo.autorizado_por = limpiar_(v('autorizado por (descuento)', 'autorizado por (cortesia)', 'autorizado por'));
      cuerpo.notas = [limpiar_(v('motivo del descuento', 'motivo de la cortesia')), limpiar_(v('notas del pago')), limpiar_(v('detalle')),
                      limpiar_(v('observacion'))].filter(String).join(' | ');
      cuerpo.enviar_entrada = ENVIAR_AL_COMPLETAR;    // el sistema solo la envía si el pago queda completo
    } else {
      // Filas del formulario anterior: se mantiene como antes (todo llega como pago por confirmar)
      cuerpo.precio_final = numero_(v('precio de entrada'));
      cuerpo.notas = [limpiar_(v('detalle')), limpiar_(v('observacion'))].filter(String).join(' | ');
      cuerpo.pago_confirmado = false;
    }

    var resp = UrlFetchApp.fetch(API_URL, {
      method: 'post', contentType: 'application/json', muteHttpExceptions: true,
      headers: {'X-API-Key': API_KEY},
      payload: JSON.stringify(cuerpo)
    });
    var codigo = resp.getResponseCode();
    var datos = {};
    try { datos = JSON.parse(resp.getContentText()); } catch (err) {}

    var celdaEstado = hoja.getRange(fila, colEstado);
    if (codigo === 200 && datos.ok) {
      if (nuevo) {
        var detalle = datos.completo ? 'COMPLETO' : 'FALTA S/ ' + datos.saldo;
        celdaEstado.setValue((datos.duplicado ? 'YA EXISTE #' : 'OK #') + datos.id + ' (' + datos.cod_cliente + ') · ' +
                             detalle + (datos.entrada_enviada ? ' · entrada enviada' : ''));
      } else {
        celdaEstado.setValue((datos.duplicado ? 'YA EXISTE #' : 'OK #') + datos.id);
      }
      return 'ok';
    }
    if (codigo === 409 && !nuevo) {                // fila antigua: mismo DNI ya registrado
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

// ============================ MODIFICAR EL FORMULARIO EXISTENTE ============================

/** Solo lee: muestra qué preguntas encontró y qué haría. No cambia nada. */
function revisarFormulario() {
  var form = abrirFormularioOAvisar_();
  if (!form) return;
  var encontrado = buscarPreguntas_(form);
  var lineas = ['Formulario: ' + form.getTitle(), ''];
  Object.keys(EXISTENTES).forEach(function (k) {
    lineas.push((encontrado.items[k] ? '✔ ' : '✘ FALTA ') + EXISTENTES[k]);
  });
  var yaHecho = !!encontrado.todos['tipo de registro'];
  lineas.push('');
  lineas.push(yaHecho ? 'AVISO: este formulario YA tiene "Tipo de registro" (ya fue modificado).'
                      : 'Todo listo para modificar. Ejecuta modificarFormularioExistente.');
  SpreadsheetApp.getUi().alert(lineas.join('\n'));
}

/**
 * Abre el formulario: primero el que está vinculado a la pestaña de respuestas (el que de verdad
 * envía datos a esta hoja) y, si falla, el ID escrito arriba. Si ninguno se puede abrir, avisa con
 * qué cuenta está corriendo el script, que es la causa más común (la cuenta no puede editarlo).
 */
function abrirFormularioOAvisar_() {
  var fallos = [];
  try {
    var hoja = SpreadsheetApp.getActive().getSheetByName(HOJA);
    var url = hoja ? hoja.getFormUrl() : null;
    if (url) return FormApp.openByUrl(url);
    fallos.push('La pestaña "' + HOJA + '" no tiene un formulario vinculado.');
  } catch (e) { fallos.push('Formulario vinculado: ' + e.message); }
  try {
    return FormApp.openById(FORM_ID);
  } catch (e) { fallos.push('Por ID: ' + e.message); }

  var cuenta = '';
  try { cuenta = Session.getEffectiveUser().getEmail(); } catch (e) {}
  SpreadsheetApp.getUi().alert(
    'No se pudo abrir el formulario, no se cambió nada.' + '\n\n' +
    'Cuenta con la que corre este script: ' + (cuenta || '(no disponible)') + '\n\n' +
    'Esa cuenta debe poder EDITAR el formulario. Abre el formulario con esa misma cuenta: si solo te deja ' +
    'responderlo o no lo encuentra, pide a su dueño que te comparta como "Editor" o ejecuta el script con ' +
    'la cuenta dueña del formulario.' + '\n\n' +
    'Detalle técnico:' + '\n- ' + fallos.join('\n- '));
  return null;
}

function buscarPreguntas_(form) {
  var todos = {};
  var items = {};
  form.getItems().forEach(function (it) { todos[sinTildes_(it.getTitle())] = it; });
  Object.keys(EXISTENTES).forEach(function (k) { items[k] = todos[EXISTENTES[k]]; });
  return {todos: todos, items: items};
}

/**
 * Agrega al formulario existente las preguntas nuevas y reordena todo en páginas:
 *   Página 1: datos del cliente, tipo de entrada, etapa de precio, asesor, tipo de registro
 *   Página "Descuento": precio acordado, quién autoriza, motivo   (solo si elige Descuento)
 *   Página "Cortesía": quién autoriza, motivo                      (solo si elige Cortesía; termina)
 *   Página "Pago": método de pago, monto pagado ahora, voucher, notas
 * Antes de cambiar nada guarda una COPIA de respaldo del formulario en tu Drive.
 */
function modificarFormularioExistente() {
  var ui = SpreadsheetApp.getUi();
  var form = abrirFormularioOAvisar_();
  if (!form) return;
  var enc = buscarPreguntas_(form);

  var faltan = Object.keys(EXISTENTES).filter(function (k) { return !enc.items[k]; });
  if (faltan.length) {
    ui.alert('No se encontraron estas preguntas, no se cambió nada:\n' +
             faltan.map(function (k) { return '• ' + EXISTENTES[k]; }).join('\n'));
    return;
  }
  if (enc.todos['tipo de registro']) {
    ui.alert('Este formulario ya fue modificado (ya existe "Tipo de registro"). No se cambió nada.');
    return;
  }

  // ---- 1) respaldo ----
  var copia = DriveApp.getFileById(form.getId()).makeCopy('COPIA de respaldo - ' + form.getTitle() + ' - ' +
                                                     Utilities.formatDate(new Date(), 'GMT', 'yyyy-MM-dd HH:mm'));

  // ---- 2) ayudas y validaciones en las preguntas existentes (no cambian sus títulos) ----
  try {
    enc.items.dni.asTextItem()
       .setHelpText('Solo números. Es el identificador de la entrada: no lo escribas mal.')
       .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^[0-9]{8,12}$')
                        .setHelpText('Escribe solo números (8 a 12), sin espacios ni puntos.').build());
  } catch (e) {}
  try {
    enc.items.celular.asTextItem()
       .setHelpText('9 dígitos. Aquí le llegará su entrada por WhatsApp.')
       .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^9[0-9]{8}$')
                        .setHelpText('Debe tener 9 dígitos y empezar con 9.').build());
  } catch (e) {}
  try {
    enc.items.monto.asTextItem()
       .setHelpText('SOLO lo que el cliente paga en este momento. Si es una separación, escribe el abono. ' +
                    'Con descuento, lo que paga ahora (el precio acordado va en la página de descuento).')
       .setValidation(FormApp.createTextValidation().requireNumber().build());
  } catch (e) {}

  // ---- 3) preguntas y páginas nuevas (se agregan al final y luego se ordenan) ----
  var etapa = form.addListItem().setTitle('Etapa de precio').setRequired(true)
      .setHelpText('El sistema toma de aquí el precio de lista de la entrada.')
      .setChoiceValues(['Preventa 1', 'Preventa 2', 'Preventa 3', 'Puerta']);
  var tipoReg = form.addMultipleChoiceItem().setTitle('Tipo de registro').setRequired(true)
      .setHelpText('Si el cliente paga por partes, vuelve a registrarlo con el MISMO DNI y elige ' +
                   '"Completar pago de una separación": el sistema suma el pago a su misma entrada.');

  var pDesc = form.addPageBreakItem().setTitle('Descuento autorizado')
      .setHelpText('Un descuento solo se registra si alguien lo autorizó.');
  var dPrecio = form.addTextItem().setTitle('Precio acordado final (S/)').setRequired(true)
      .setHelpText('Lo que cuesta la entrada CON el descuento (no lo que paga ahora).')
      .setValidation(FormApp.createTextValidation().requireNumber().build());
  var dAutor = form.addTextItem().setTitle('Autorizado por (descuento)').setRequired(true)
      .setHelpText('Nombre de quien autorizó el descuento.');
  var dMotivo = form.addParagraphTextItem().setTitle('Motivo del descuento').setRequired(true);

  var pCort = form.addPageBreakItem().setTitle('Cortesía (gratis)')
      .setHelpText('La entrada se registra sin costo y se envía sola.');
  var cAutor = form.addTextItem().setTitle('Autorizado por (cortesia)').setRequired(true);
  var cMotivo = form.addParagraphTextItem().setTitle('Motivo de la cortesia').setRequired(true);

  var pPago = form.addPageBreakItem().setTitle('Pago');
  var notas = form.addParagraphTextItem().setTitle('Notas del pago')
      .setHelpText('Opcional. Ej.: número de operación.');

  // ---- 4) orden final de todas las preguntas ----
  var I = enc.items;
  var orden = [I.nombres, I.dni, I.celular, I.correo, I.tipo, etapa, I.asesor, tipoReg,
               pDesc, dPrecio, dAutor, dMotivo,
               pCort, cAutor, cMotivo,
               pPago, I.metodo, I.monto, I.voucher, notas];
  orden.forEach(function (item, i) { form.moveItem(item.getIndex(), i); });

  // ---- 5) navegación según el tipo de registro ----
  pDesc.setGoToPage(pPago);
  pCort.setGoToPage(FormApp.PageNavigationType.SUBMIT);
  tipoReg.setChoices([
    tipoReg.createChoice('Pago completo', pPago),
    tipoReg.createChoice('Separación (abono parcial)', pPago),
    tipoReg.createChoice('Completar pago de una separación', pPago),
    tipoReg.createChoice('Descuento autorizado', pDesc),
    tipoReg.createChoice('Cortesía (gratis)', pCort)
  ]);

  // ---- 6) la descripción conserva lo que ya tenía ----
  form.setDescription((form.getDescription() || '') +
    '\n\nSi el cliente paga por partes (separación), regístralo cada vez con el MISMO DNI y elige ' +
    '"Completar pago de una separación". Cualquier descuento o cortesía necesita decir quién lo autorizó.');

  ui.alert('Formulario modificado ✔\n\n' +
           'Se guardó una copia de respaldo en tu Drive:\n' + copia.getUrl() + '\n\n' +
           'Compártelo con tu personal con el mismo enlace de siempre.\n' +
           'Las respuestas nuevas llegarán a la pestaña "' + HOJA + '" con columnas nuevas a la derecha.');
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

/** Lee la primera columna de la lista de nombres alternativos que tenga un valor en esa fila. */
function leer_(hoja, fila, enc, nombres) {
  for (var i = 0; i < nombres.length; i++) {
    var col = enc[nombres[i]];
    if (!col) continue;
    var valor = hoja.getRange(fila, col).getValue();
    if (valor !== '' && valor !== null && valor !== undefined) return valor;
  }
  return '';
}

/** Devuelve un correo usable o '' (descarta '00', '00@gmail.com', 'Solo Whatsapp', teléfonos, comillas). */
function correo_(t) {
  var m = String(t || '').replace(/["']/g, ' ').match(/[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}/);
  if (!m) return '';
  var c = m[0].toLowerCase();
  return /^0+$/.test(c.split('@')[0]) ? '' : c;
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
