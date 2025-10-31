import os
import requests
import redis
import json # <-- ADICIONE ESTA LINHA
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langchain.chains import ConversationChain
# Mude a linha abaixo para importar ChatMessageHistory
from langchain.memory import ConversationBufferMemory, ChatMessageHistory
from langchain_openai import ChatOpenAI
# Adicione estas duas novas importações do LangChain
from langchain_core.messages import messages_from_dict, messages_to_dict
# --- 1. CONFIGURAÇÃO INICIAL ---
from datetime import datetime
import pytz

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

# --- 4. A ROTA DO WEBHOOK (Versão com Memória JSON no Redis) ---

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

        numero_destino = dados_msg.get("key", {}).get("remoteJid")
        mensagem_usuario = dados_msg.get("message", {}).get("conversation")

        # --- NOVO: INJETAR DATA/HORA ATUAL ---
    # 1. Define o fuso horário correto (Brasil - São Paulo)
        fuso_horario_sp = pytz.timezone("America/Sao_Paulo")

    # 2. Pega a data e hora atuais nesse fuso
        agora_sp = datetime.now(fuso_horario_sp)

    # 3. Formata como um texto legível
        agora_formatado = agora_sp.strftime("%A, %d de %B de %Y, %H:%M:%S (%Z)")

        print(f"Injetando contexto de hora: {agora_formatado}")

    # 4. Cria o "super-prompt" que dá o contexto para a IA
        mensagem_com_contexto = f"""
    (Contexto importante para a IA: A data e hora atual no Brasil é: {agora_formatado}. 
    Responda à pergunta do usuário abaixo com base nesse contexto.)

    Pergunta do Usuário: "{mensagem_usuario}"
    """
    # --- FIM DO NOVO BLOCO ---

        if not mensagem_usuario or not numero_destino:
            print("Ignorando (sem texto ou sem número de destino)")
            return jsonify({"status": "ignorado"}), 200

        print(f"Mensagem de {numero_destino}: {mensagem_usuario}")

        # --- ETAPA 2: "CÉREBRO" (COM MEMÓRIA DINÂMICA DO REDIS) ---

        if not r: # Se o Redis não conectou, pare aqui
             print("ERRO: Sem conexão com o Redis para carregar/salvar memória.")
             return jsonify({"status": "erro_redis"}), 500

        # --- LÓGICA DE CARREGAMENTO (CORRIGIDA) ---
        memoria_usuario = None
        try:
            # 1. Tenta buscar o *JSON* do histórico no Redis
            historico_json_string = r.get(numero_destino)

            if historico_json_string:
                # 2. Transforma o texto JSON numa lista de dados do Python
                messages_data = json.loads(historico_json_string)
                # 3. Transforma os dados em objetos de Mensagem (HumanMessage, AIMessage)
                messages_carregados = messages_from_dict(messages_data)
                # 4. Cria o objeto de memória *com* o histórico carregado
                memoria_usuario = ConversationBufferMemory(
                    chat_memory=ChatMessageHistory(messages=messages_carregados),
                    return_messages=True # É uma boa prática
                )
                print(f"Histórico carregado para: {numero_destino}")
            else:
                # Se não há histórico, cria uma memória vazia
                memoria_usuario = ConversationBufferMemory(return_messages=True)
                print(f"Nenhum histórico encontrado. Nova conversa para: {numero_destino}")

        except Exception as e:
            print(f"ERRO ao ler ou recriar do Redis: {e}")
            memoria_usuario = ConversationBufferMemory(return_messages=True) # Continua com memória vazia

        # --- FIM DA LÓGICA DE CARREGAMENTO ---

        # 3. Cria uma CADEIA DE CONVERSA *SÓ PARA ESTE USUÁRIO*
        conversa_usuario = ConversationChain(
            llm=llm,
            memory=memoria_usuario, # Usa a memória específica dele
            verbose=True
        )

        # 4. Invoca o cérebro (MUDANÇA IMPORTANTE: usa um dicionário)
        # A versão antiga do 'invoke' com string está obsoleta.
        # O 'invoke' espera um dicionário. A 'input_key' padrão é "input".
        resposta_ia_obj = conversa_usuario.invoke({"input": mensagem_com_contexto})
        resposta_ia_texto = resposta_ia_obj['response']
        print(f"Resposta da IA: {resposta_ia_texto}")

        # --- LÓGICA DE SALVAMENTO (CORRIGIDA) ---
        try:
            # 5. Pega a *lista de mensagens* da memória (não o texto)
            novo_historico_msgs = conversa_usuario.memory.chat_memory.messages
            # 6. Converte os objetos de mensagem para dados (para JSON)
            messages_data = messages_to_dict(novo_historico_msgs)
            # 7. Transforma os dados em texto JSON
            novo_historico_json_string = json.dumps(messages_data)
            # 8. Salva o JSON no Redis
            r.set(numero_destino, novo_historico_json_string)
            print(f"Histórico salvo para: {numero_destino}")
        except Exception as e:
            print(f"ERRO ao salvar no Redis: {e}")
        # --- FIM DA LÓGICA DE SALVAMENTO ---

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