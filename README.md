# 🤖 Bot de WhatsApp com IA (LangChain + Evolution API + Redis)

Este é um chatbot de IA totalmente funcional para WhatsApp, construído com Python, LangChain e OpenAI. O projeto é implantado (deploy) numa VPS (através do EasyPanel) usando Docker, garantindo um serviço robusto e escalável.

O bot é capaz de:

* Receber mensagens de WhatsApp em tempo real via webhooks da Evolution API.
* Entender o contexto da conversa usando o `gpt-4o` da OpenAI.
* Manter um histórico de memória persistente e único por usuário usando um banco de dados Redis.
* Responder ao usuário diretamente no WhatsApp.
* Injetar automaticamente a data e hora atuais no contexto da IA, permitindo-lhe responder a perguntas como "Que horas são?".

---

## 🚀 Tecnologias Utilizadas

* **Backend:** Python 3.12
* **Servidor Web:** Flask (para o webhook), Gunicorn (para produção)
* **Inteligência Artificial:** LangChain (`ConversationChain`), OpenAI (`gpt-4o`)
* **Gateway de WhatsApp:** Evolution API (v2)
* **Banco de Dados (Memória):** Redis
* **Deploy (Implantação):** EasyPanel
* **Containerização:** Docker (via `Dockerfile`)

---

## 🚀 Instalação e Deploy

A implantação deste projeto é feita via Docker, orquestrada pelo EasyPanel. A parte mais desafiadora e instrutiva deste projeto foi a implantação.

Após várias tentativas falhadas com Nixpacks (devido a conflitos de `venv` e `PATH`), a solução definitiva foi usar um `Dockerfile` explícito.

### 1. Dockerfile

Este ficheiro é a "receita de bolo" que diz ao EasyPanel como construir o ambiente do zero, garantindo 100% de consistência:

1.  Começa com a imagem oficial `python:3.12-slim`.
2.  Copia o `requirements.txt`.
3.  Executa `pip install --no-cache-dir -r requirements.txt`, instalando todas as bibliotecas (como `langchain`, `flask`, `redis`) globalmente dentro do contêiner. O `--no-cache-dir` foi crucial para resolver problemas de cache de build.
4.  Copia o resto do código (ex: `app.py`).
5.  Define o comando final (`CMD`) para iniciar o servidor Gunicorn, que é robusto para produção.

**Exemplo de `Dockerfile` (baseado na descrição):**
```dockerfile
# Usa uma imagem base leve do Python
FROM python:3.12-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia e instala as dependências primeiro, para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código da aplicação
COPY . .

# Expõe a porta que o Gunicorn/Flask usará
EXPOSE 5000

# Comando para rodar a aplicação em produção
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
