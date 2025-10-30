# 1. Comece com a imagem oficial do Python 3.12
FROM python:3.12-slim

# 2. Defina o diretório de trabalho
WORKDIR /app

# 3. Copie o requirements.txt primeiro (para cache)
COPY requirements.txt .

# 4. Instale as bibliotecas GLOBALMENTE (sem venv)
# (Note que é 'pip' e 'gunicorn', não './venv/bin/...')
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copie o resto do seu código (app.py, etc)
COPY . .

# 6. Diga ao contêiner para rodar o Gunicorn (que agora está global)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "app:app"]