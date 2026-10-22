# Prompt para pegar en Claude Code

Pega esto en Claude Code, abierto dentro de esta carpeta:

```
Este repositorio mide el área quemada del incendio de Manantay (Ucayali) en octubre de 2026 con dNBR de
Sentinel-2 y compara los focos de esta semana con 2012-2025 (retos A + E de mi tarea). Los scripts ya
están escritos. Quiero que:

1. Crees un entorno virtual e instales requirements.txt.
2. Corras 01_focos.py y me muestres cuántos focos tiene el incendio y sus fechas. Si no hay focos en
   Manantay, detente y dime qué incendio cercano sí está activo.
3. Corras 02_dnbr.py, pero ANTES de aceptar el resultado muéstrame la tabla de imágenes candidatas con
   su % de nubes y explícame por qué se eligieron esas dos fechas. Si alguna tiene más de 30 % de nubes,
   propón otra y vuelve a correr con --pre / --post.
4. Abre outputs/mapa_dnbr.png y dime si algo se ve raro (nubes, ríos, chacras).
5. Corras 03_anio_record.py y 04_readme.py.
6. Hagas commit y push a mi repositorio de GitHub.

Explícame cada decisión antes de correrla. No cambies el método sin preguntarme.
```

Si el wifi falla con Planetary Computer, sube la carpeta a Google Colab y corre los mismos pasos allí.
