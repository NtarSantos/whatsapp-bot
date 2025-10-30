import os  # Para acessar variáveis de ambiente
import requests  # Para fazer a requisição HTTP (a "Voz")
from flask import Flask, request, jsonify  # Para o servidor web (a "Orelha")
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.chains.conversation.base import ConversationChain
from langchain.memory import ConversationBufferMemory


# --- 1. CONFIGURAÇÃO INICIAL ---

# Carrega as variáveis do arquivo .env (como a OPENAI_API_KEY)
load_dotenv()

# VERIFIQUE: Cole aqui a URL que você copiou do webhook.site
# É para cá que o bot vai "fingir" que está enviando a resposta do WhatsApp.
URL_DE_RESPOSTA_SIMULADA = "https://webhook.site/5b01ddb6-8886-4e09-849b-1a659a3a30f5" 

# --- 2. INICIALIZANDO O "CÉREBRO" (LangChain com Memória) ---

# Inicializa o modelo de IA que vamos usar
# temperature=0.7 dá um bom equilíbrio entre respostas corretas e criativas
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# Inicializa a memória. É ela que guarda o histórico.
# Sem isso, ele não lembraria da pergunta anterior.
memoria = ConversationBufferMemory()

# Cria a "Cadeia" (Chain) de conversação
# Esta é a peça central do LangChain que une o Modelo (llm) e a Memória.
# verbose=True faz ele imprimir no terminal o que está pensando (ótimo para aprender)
conversa = ConversationChain(
    llm=llm,
    memory=memoria,
    verbose=True 
)

# --- 3. INICIALIZANDO A "ORELHA" (Servidor Flask) ---

# Cria a aplicação web Flask
app = Flask(__name__)

# --- 4. A ROTA DO WEBHOOK ---
# É aqui que a "mágica" acontece.

# Esta função vai rodar sempre que alguém (o WhatsApp)
# enviar uma requisição POST para a URL: http://seusite.com/webhook
@app.route("/webhook", methods=["POST"])
def receber_mensagem():
    
    print(">>> Webhook recebido!")

    # 1. PEGAR A MENSAGEM QUE CHEGOU
    # Pegamos os dados (JSON) que o WhatsApp (simulado) enviou
    dados_webhook = request.json
    
    # IMPORTANTE: Estamos *simulando* a estrutura de uma mensagem.
    # Em um webhook real, a mensagem estaria "escondida" (ex: dados['entry'][0]['messages'][0]['text']['body'])
    # Para nosso teste, vamos supor que o JSON é simples: { "mensagem": "Oi, tudo bem?" }
    try:
        mensagem_usuario = dados_webhook['mensagem']
        print(f"Mensagem do usuário: {mensagem_usuario}")
    except KeyError:
        # Se o JSON não tiver a chave "mensagem"
        print("Erro: JSON recebido não continha a chave 'mensagem'")
        return jsonify({"status": "erro", "resposta": "JSON inválido"}), 400

    # 2. PENSAR NA RESPOSTA (O "Cérebro")
    # Enviamos a mensagem do usuário para a cadeia do LangChain
    # O .invoke() automaticamente usa a memória e o modelo para gerar a resposta.
    resposta_ia = conversa.invoke(mensagem_usuario)

    print(f"Resposta da IA: {resposta_ia['response']}")

    # 3. ENVIAR A RESPOSTA (A "Voz")
    # Agora, simulamos o envio dessa resposta de volta para a API do WhatsApp
    
    # Preparamos os dados que a API do WhatsApp (simulada) espera
    dados_para_envio = {
        "numero_destino": "123456789", # Apenas um exemplo
        "resposta": resposta_ia['response']
    }

    try:
        # Usamos a biblioteca 'requests' para enviar nossa resposta para o Webhook.site
        requests.post(URL_DE_RESPOSTA_SIMULADA, json=dados_para_envio)
        print("Resposta enviada para o Webhook.site com sucesso!")
        
    except Exception as e:
        print(f"Erro ao enviar resposta para o Webhook.site: {e}")

    # Finalmente, respondemos ao webhook original dizendo "Ok, recebi"
    return jsonify({"status": "sucesso"}), 200

# --- 5. RODAR O SERVIDOR ---

# Esta parte só é usada se você rodar "python app.py" diretamente
# No EasyPanel, o Gunicorn vai cuidar disso, mas é bom ter.
if __name__ == "__main__":
    # Roda o servidor na porta 5000, visível para a rede (0.0.0.0)
    app.run(host="0.0.0.0", port=5000)