#!/bin/sh
# Todas las pruebas de la app, una detras de otra: abren ventanas y comparten el INI.
# Cada una con un limite de tiempo (colgarse cuenta como fallo) y diciendo que codigo ha cargado.
AQUI="$(cd "$(dirname "$0")" && pwd)"
ENCE_RAIZ="$(cd "$AQUI/../.." && pwd)"
: "${ENCE_GALERA_DATOS:?falta ENCE_GALERA_DATOS}"
PLANES="$ENCE_RAIZ/99-Test/05_planes"
PY=/c/e2s/python.exe
LIMITE=1200
SALIDA="$AQUI/regresion_ultima.txt"
export PYTHONIOENCODING=utf-8
cd "$AQUI" || exit 1
export ENCE_AJUSTES_PRUEBA="$TEMP/ence_galera/99-Test/ajustes"     # nunca el INI del usuario
mkdir -p "$ENCE_AJUSTES_PRUEBA/CIRCE"

corre() {  # corre <patron de lineas> <lineas> <orden...>
  patron=$1; n=$2; shift 2
  t0=$(date +%s); timeout "$LIMITE" "$PY" "$@" > "$SALIDA" 2>&1
  rc=$?; echo "  $(( $(date +%s) - t0 )) s"
  if [ -n "$patron" ]; then grep -E "$patron" "$SALIDA" | tail -"$n"; else tail -"$n" "$SALIDA"; fi
  [ "$rc" -eq 124 ] && echo "COLGADA: $* (limite $LIMITE s)"
  [ "$rc" -ne 0 ] && [ "$rc" -ne 124 ] && echo "SALIDA $rc: $*"
  return 0
}

for p in prueba_indicador.py prueba_tabla.py prueba_3d_app.py prueba_gases_app.py prueba_dos_motores.py prueba_previa.py "prueba_previa.py vacio" prueba_escalas.py prueba_emplazamiento.py prueba_capas_terminal.py probar_planes.py prueba_iconos.py prueba_viento.py; do
  echo "=== $p"
  # shellcheck disable=SC2086
  corre "^CODIGO|^MAL|FALLOS|Traceback|Error:" 8 $p
done
for e in oscuro claro noche contraste; do
  echo "=== estilos fresco $e"
  corre "^CODIGO|^MAL|Traceback|Error:|^hecho" 4 prueba_estilos.py fresco "$e"
done
echo "=== estilos vivo"
corre "^CODIGO|^MAL|Traceback|Error:|cambio|s$" 7 prueba_estilos.py vivo
echo "=== estilos comparar"
corre "" 7 prueba_estilos.py comparar
cd "$PLANES" || exit 1
for p in prueba_calcular.py prueba_penacho.py ../08_gases/prueba_gases.py; do
  echo "=== $p"
  corre "^MAL|  MAL|FALLOS|Traceback|Error:" 8 "$p"
done
cd "$AQUI" || exit 1
echo "=== prueba_main.py"
corre "" 16 prueba_main.py
echo "=== FIN"
