# Publicar LAY en otra cuenta de GitHub

El código ya viene listo para compilarse solo en la nube. No necesitas Python ni Windows para generar el `.exe`.

## Pasos

1. Crea un repositorio nuevo en tu otra cuenta, por ejemplo `micuenta/LAY`. Puede ser **público**: así otras personas descargan el instalador sin iniciar sesión.
2. Sube el contenido de esta carpeta (la carpeta `LAY/` del zip). Tienes dos formas:
   - **Desde la web:** "Add file" → "Upload files" y arrastra todo, **incluida la carpeta oculta `.github/`**. Sin ella no se compila nada.
   - **Con Git:**
     ```bash
     cd LAY
     git init -b main
     git add .
     git commit -m "LAY"
     git remote add origin https://github.com/micuenta/LAY.git
     git push -u origin main
     ```
3. En el repo, ve a **Settings → Actions → General → Workflow permissions** y elige **"Read and write permissions"**. Es necesario para que publique el Release.
4. Cada vez que subas cambios a `main`, GitHub Actions:
   - compila `LAY_Setup_<versión>.exe` y `LAY_portable_<versión>.zip` en un Windows real (unos 15 minutos);
   - corre el diagnóstico del exe (manos, voz, navegador, apps…);
   - publica el **Release v<versión>** con los dos archivos.
5. El aviso de "hay una versión nueva" de LAY apunta automáticamente al repo donde se compiló. Tus usuarios se actualizan desde **tu** repo, no desde el original.

## Cambiar la versión

Edita `version = "..."` en `pyproject.toml` y sube el cambio: sale un Release nuevo con ese número.

## Qué NO va en el repo (y está bien así)

- `.env` con claves, la carpeta `~/.lay` de cada usuario (memoria, chat, libros, modelos, tokens de correo). Todo eso vive en cada PC.
- Los modelos de IA (Ollama): el instalador los descarga en cada PC según su RAM.

## Licencia

Antes de hacerlo público, agrega un archivo `LICENSE` con la licencia que prefieras (por ejemplo MIT si quieres que cualquiera pueda reutilizarlo). Sin licencia, el código es visible pero nadie tiene permiso legal de reutilizarlo.
