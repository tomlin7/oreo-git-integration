rmdir /s /q build dist
pyinstaller --clean -F -c --i resources/logo.ico cli/oreo-git.py