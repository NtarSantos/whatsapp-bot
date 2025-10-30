import os
import requests
import redis # <-- NOVO: Importa a biblioteca do Redis
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

# --- 1. CONFIGURAÇÃO INICIAL ---

load_dotenv()

# Puxa as chaves do Ambiente do EasyPanel
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # LangChain agora lê isto

# --- NOVO: CONEXÃO COM O REDIS ---
# Conecta-se ao seu serviço Redis usando as variáveis de ambiente
try:
    r = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True # <-- Importante: decodifica de bytes para string
    )
    r.ping() # Testa a conexão
    print(">>> Conectado ao Redis com sucesso!")
except Exception as e:
    print(f">>> FALHA AO CONECTAR NO REDIS: {e}")
    r = None # Define como None se a conexão falhar

# --- 2. INICIALIZANDO O "CÉREBRO" (LangChain) ---
# O 'llm' pode ser global, pois não guarda estado.
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# !! MUDANÇA IMPORTANTE: REMOVEMOS A 'memoria' e 'conversa' GLOBAIS !!
# Elas agora serão criadas DENTRO de cada pedido.

# --- 3. INICIALIZANDO A "ORELHA" (Flask) ---
app = Flask(__name__)


# --- 4. A ROTA DO WEBHOOK (Versão com Memória Única) ---

@app.route("/webhook", methods=["POST"])
def receber_mensagem():
    
    print(">>> Webhook da Evolution API recebido!")
    dados_webhook = request.json

    try:
        # --- ETAPA 1: "DESEMPACOTAR" (Igual a antes) ---
        if dados_webhook.get("event") != "messages.upsert":
            print("Ignorando evento (não é 'messages.upsert')")
            return jsonify({"status": "ignorado"}), 200

        dados_msg = dados_webhook.get("data", {})
        
        if dados_msg.get("key", {}).get("fromMe") == True:
            print("Ignorando mensagem (fromMe é true)")
            return jsonify({"status": "ignorado"}), 200

        # A "Chave" do nosso banco de dados: o número do usuário
        numero_destino = dados_msg.get("key", {}).get("remoteJid")
        mensagem_usuario = dados_msg.get("message", {}).get("conversation")

        if not mensagem_usuario or not numero_destino:
            print("Ignorando (sem texto ou sem número de destino)")
            return jsonify({"status": "ignorado"}), 200
            
        print(f"Mensagem de {numero_destino}: {mensagem_usuario}")

        # --- ETAPA 2: "CÉREBRO" (COM MEMÓRIA DINÂMICA DO REDIS) ---
        
        if not r: # Se o Redis não conectou, pare aqui
             print("ERRO: Sem conexão com o Redis para carregar/salvar memória.")
             return jsonify({"status": "erro_redis"}), 500

        # 1. Cria uma memória nova e vazia para este pedido
        memoria_usuario = ConversationBufferMemory()
        
        # 2. Tenta carregar o histórico antigo do Redis
        try:
            # Usamos o 'numero_destino' como a chave única
            historico_string = r.get(numero_destino)
            if historico_string:
                # Carrega o histórico salvo na memória
                memoria_usuario.buffer = historico_string
                print(f"Histórico carregado para: {numero_destino}")
            else:
                print(f"Nenhum histórico encontrado. Nova conversa para: {numero_destino}")
        except Exception as e:
            print(f"ERRO ao ler do Redis: {e}")
            # Continua com a memória vazia

        # 3. Cria uma CADEIA DE CONVERSA *SÓ PARA ESTE USUÁRIO*
        conversa_usuario = ConversationChain(
            llm=llm,
            memory=memoria_usuario, # Usa a memória específica dele
            verbose=True
        )

        # 4. Invoca o cérebro (igual a antes)
        resposta_ia_obj = conversa_usuario.invoke(mensagem_usuario)
        resposta_ia_texto = resposta_ia_obj['response']
        print(f"Resposta da IA: {resposta_ia_texto}")

        # 5. SALVA o novo histórico de volta no Redis
        try:
            # Pega o buffer atualizado (pergunta + resposta)
            novo_historico_string = conversa_usuario.memory.buffer 
            # Salva no Redis, usando o número como chave
            r.set(numero_destino, novo_historico_string)
            print(f"Histórico salvo para: {numero_destino}")
        except Exception as e:
            print(f"ERRO ao salvar no Redis: {e}")

        # --- ETAPA 3: "VOZ" (Igual a antes) ---
        
        headers = { "apikey": EVOLUTION_API_KEY, "Content-Type": "application/json" }
        payload_resposta = {
            "number": numero_destino,
            "text": resposta_ia_texto
        }
        requests.post(EVOLUTION_API_URL, json=payload_resposta, headers=headers)
        print("Resposta enviada para a Evolution API com sucesso!")
        
        return jsonify({"status": "sucesso"}), 200

    except Exception as e:
        print(f"Erro interno no processamento: {e}")
        return jsonify({"status": "erro_interno"}), 500

# --- 5. RODAR O SERVIDOR ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)