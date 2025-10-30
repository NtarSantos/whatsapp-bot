# 1. Comece com uma imagem oficial leve do Python 3.12
FROM python:3.12-slim
# 3. Defina o diretório de trabalho dentro do contêiner
WORKDIR /app
# 4. Copie *apenas* o requirements.txt primeiro (para cache)
COPY requirements.txt .
# 5. Crie o venv e instale as bibliotecas DENTRO dele (nosso comando antigo)
RUN python3.12 -m venv venv && ./venv/bin/pip install -r requirements.txt
# 6. Copie o *resto* do seu código (app.py)
COPY . .
# 7. Diga ao contêiner para usar o Gunicorn de dentro do venv
CMD ["./venv/bin/gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "app:app"]