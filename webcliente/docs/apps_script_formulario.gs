/**
 * Script DENTRO DEL FORMULARIO "EDE 2.0": agrega separaciones, descuentos y cortesías
 * ----------------------------------------------------------------------------------
 * Este script se pega en el editor de scripts DEL FORMULARIO (no en el de la hoja):
 *   Abre el formulario (modo edición) → menú ⋮ (tres puntos, arriba a la derecha) →
 *   "Editor de secuencias de comandos" → borra lo que haya, pega este archivo y guarda.
 *
 * Como vive dentro del formulario, siempre corre con una cuenta que puede editarlo
 * (no hay problemas de permisos entre la hoja y el formulario).
 *
 * USO
 *  1. Ejecuta  revisarEsteFormulario  (solo lee, no cambia nada) y acepta los permisos.
 *  2. Ejecuta  modificarEsteFormulario . Antes de cambiar nada guarda una COPIA en tu Drive.
 *
 * No borra ni renombra ninguna pregunta existente ni toca las respuestas anteriores.
 */

// Preguntas que YA existen (se buscan por su título, sin tildes ni mayúsculas)
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

/** Solo lee: muestra qué preguntas encontró. No cambia nada. */
function revisarEsteFormulario() {
  var form = FormApp.getActiveForm();
  var encontrado = buscarPreguntas_(form);
  var lineas = ['Formulario: ' + form.getTitle(), ''];
  Object.keys(EXISTENTES).forEach(function (k) {
    lineas.push((encontrado.items[k] ? '✔ ' : '✘ FALTA ') + EXISTENTES[k]);
  });
  lineas.push('');
  lineas.push(encontrado.todos['tipo de registro']
    ? 'AVISO: este formulario YA tiene "Tipo de registro" (ya fue modificado).'
    : 'Todo listo para modificar. Ejecuta modificarEsteFormulario.');
  FormApp.getUi().alert(lineas.join('\n'));
}

/**
 * Agrega las preguntas nuevas y reordena todo en páginas:
 *   Página 1: datos del cliente, tipo de entrada, etapa de precio, asesor, tipo de registro
 *   Página "Descuento": precio acordado, quién autoriza, motivo   (solo si elige Descuento)
 *   Página "Cortesía": quién autoriza, motivo                      (solo si elige Cortesía; termina)
 *   Página "Pago": método de pago, monto pagado ahora, voucher, notas
 */
function modificarEsteFormulario() {
  var ui = FormApp.getUi();
  var form = FormApp.getActiveForm();
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
           'El enlace para tu personal es el mismo de siempre.');
}

function buscarPreguntas_(form) {
  var todos = {};
  var items = {};
  form.getItems().forEach(function (it) { todos[sinTildes_(it.getTitle())] = it; });
  Object.keys(EXISTENTES).forEach(function (k) { items[k] = todos[EXISTENTES[k]]; });
  return {todos: todos, items: items};
}

function limpiar_(t) { return String(t === null || t === undefined ? '' : t).replace(/\s+/g, ' ').trim(); }

function sinTildes_(t) {
  return limpiar_(t).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}
