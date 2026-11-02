# Reglas del proyecto para Claude Code

## Reglas obligatorias del usuario

1. **No eliminar archivos sin autorización expresa.** Esto incluye archivos del repositorio, archivos temporales y archivos creados en la misma sesión. Antes de borrar, mover o sobrescribir un archivo existente, pedir confirmación.
2. **Preguntar antes de emitir cualquier documento.** Antes de crear un documento nuevo (código, guías, fichas, informes), confirmar con el usuario.
3. **Nunca dejar marcadores visibles en los documentos.** Nada de textos como "[pendiente]", "TODO", "XXX", "completar" o valores de ejemplo para rellenar. Si un dato no existe, la línea se omite.
4. **Solo fuentes oficiales colombianas.** La jurisprudencia debe provenir exclusivamente de las entidades oficiales listadas en `jurisprudencia/fuentes.py`. No agregar dominios no oficiales ni de otros países.

## Forma de trabajo

- Responder en español, de forma crítica, precisa y estructurada. No dar la razón por defecto: señalar errores y proponer alternativas.
- Si no hay certeza sobre algo, decirlo claramente.
- Formato de las fichas: Markdown (`.md`), confirmado por el usuario.
- Antes de hacer push, ejecutar las pruebas: `python -m pytest -q`.
