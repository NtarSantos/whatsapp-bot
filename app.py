import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

# --- 1. CONFIGURAÇÃO INICIAL (AGORA COM MAIS CHAVES) ---

load_dotenv()

# Puxa as chaves do Ambiente do EasyPanel
# (Certifique-se de adicionar as 2 NOVAS chaves no EasyPanel!)
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")

# Esta é a URL *interna* do Docker no EasyPanel.
# É mais rápida e segura que a URL pública.
# (Se seu serviço no EasyPanel não se chamar 'evolution-api', mude aqui)
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://evolution-api:8080/message/sendText")


# --- 2. INICIALIZANDO O "CÉREBRO" (LangChain) ---
# (Idêntico ao anterior)
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
memoria = ConversationBufferMemory()
conversa = ConversationChain(
    llm=llm,
    memory=memoria,
    verbose=True
)

# --- 3. INICIALIZANDO A "ORELHA" (Flask) ---
app = Flask(__name__)


# --- 4. A ROTA DO WEBHOOK (Versão Evolution API) ---

@app.route("/webhook", methods=["POST"])
def receber_mensagem():
    
    print(">>> Webhook da Evolution API recebido!")
    dados_webhook = request.json # O JSON começa com {"event": ...}

    try:
        # ETAPA 1: "Desempacotar" a mensagem (com base no JSON que você mandou)
        
        # Ignora eventos que não são mensagens novas (ex: status de entrega)
        if dados_webhook.get("event") != "messages.upsert":
            print("Ignorando evento (não é 'messages.upsert')")
            return jsonify({"status": "ignorado"}), 200

        # Pega o "pacote" de dados da mensagem
        dados_msg = dados_webhook.get("data", {})
        
        # IGNORA MENSAGENS DO PRÓPRIO BOT (CRUCIAL!)
        # Se 'fromMe' for 'true', o bot para e não responde a si mesmo.
        if dados_msg.get("key", {}).get("fromMe") == True:
            print("Ignorando mensagem (fromMe é true)")
            return jsonify({"status": "ignorado"}), 200

        # Pega o número de quem enviou (ex: 5561...s.whatsapp.net ou 123...@g.us)
        numero_destino = dados_msg.get("key", {}).get("remoteJid")
        
        # Pega o texto da mensagem (do campo 'conversation')
        mensagem_usuario = dados_msg.get("message", {}).get("conversation")

        # Se não houver texto (ex: imagem, áudio, etc.), ignora
        if not mensagem_usuario:
            print("Ignorando (sem texto em 'conversation')")
            return jsonify({"status": "ignorado"}), 200
            
        print(f"Mensagem de {numero_destino}: {mensagem_usuario}")

        # ETAPA 2: "Cérebro" (LangChain) pensa na resposta
        # AVISO: Este bot básico tem uma memória *compartilhada*.
        # Se duas pessoas falarem com ele ao mesmo tempo, ele vai misturar as conversas.
        # (Para aprender, está perfeito. Para produção, precisaríamos de memórias por usuário).
        resposta_ia_obj = conversa.invoke(mensagem_usuario)
        resposta_ia_texto = resposta_ia_obj['response']
        
        print(f"Resposta da IA: {resposta_ia_texto}")

        # ETAPA 3: "Voz" (Enviar resposta pela Evolution API)
        
        # Prepara os headers da requisição com sua chave
        headers = {
            "apikey": EVOLUTION_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Prepara o JSON da mensagem de resposta (formato da Evolution)
        payload_resposta = {
    "number": numero_destino,
    "text": resposta_ia_texto
        }

        # Envia a resposta!
        requests.post(EVOLUTION_API_URL, json=payload_resposta, headers=headers)
        
        print("Resposta enviada para a Evolution API com sucesso!")
        
        # Responde 200 (OK) para o webhook
        return jsonify({"status": "sucesso"}), 200

    except Exception as e:
        # Se qualquer coisa der errado (parse do JSON, etc.)
        print(f"Erro interno no processamento: {e}")
        return jsonify({"status": "erro_interno"}), 500

# --- 5. RODAR O SERVIDOR ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)