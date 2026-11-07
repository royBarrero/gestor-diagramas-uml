/// "Hace 12 min", "Ayer", "Hace 3 días"... — mismo criterio que
/// frontend/src/utils/fechaRelativa.js.
String fechaRelativa(DateTime? fecha) {
  if (fecha == null) return 'Sin cambios todavía';

  final segundos = DateTime.now().difference(fecha).inSeconds;
  if (segundos < 60) return 'Hace un momento';

  final minutos = segundos ~/ 60;
  if (minutos < 60) return 'Hace $minutos min';

  final horas = minutos ~/ 60;
  if (horas < 24) return horas == 1 ? 'Hace 1 hora' : 'Hace $horas horas';

  final dias = horas ~/ 24;
  if (dias == 1) return 'Ayer';
  if (dias < 7) return 'Hace $dias días';

  final semanas = dias ~/ 7;
  if (dias < 30) return semanas == 1 ? 'La semana pasada' : 'Hace $semanas semanas';

  final meses = dias ~/ 30;
  if (dias < 365) return meses == 1 ? 'El mes pasado' : 'Hace $meses meses';

  final anios = dias ~/ 365;
  return anios == 1 ? 'El año pasado' : 'Hace $anios años';
}

/// Hora de un mensaje: hoy solo "14:05"; otro día también la fecha "03/11 14:05".
/// El backend manda la fecha con zona horaria; se muestra en la hora del celular.
String formatearHora(DateTime fechaRecibida) {
  final fecha = fechaRecibida.toLocal();
  String dos(int n) => n.toString().padLeft(2, '0');
  final hora = '${dos(fecha.hour)}:${dos(fecha.minute)}';
  final hoy = DateTime.now();
  final esHoy = fecha.year == hoy.year && fecha.month == hoy.month && fecha.day == hoy.day;
  return esHoy ? hora : '${dos(fecha.day)}/${dos(fecha.month)} $hora';
}
