import os
import json
import random  # Importado para embaralhar as chaves e distribuir o consumo
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors  # Importado para capturar falhas específicas da API (como limite de requisição)
from dotenv import load_dotenv

from config import ENTIDADE_SCHEMA, SYSTEM_INSTRUCTION


load_dotenv()

app = Flask(__name__)
CORS(app)


def obter_chaves_api() -> list:
    """
    Carrega e limpa as chaves, tratando automaticamente caso o usuário
    tenha configurado múltiplas chaves no singular (GEMINI_API_KEY) ou plural.
    """
    # Tenta obter de qualquer uma das duas variáveis
    api_keys_str = os.getenv("GEMINI_API_KEYS")  
    
    if api_keys_str:
        # Se houver vírgula, divide a string em várias chaves
        if "," in api_keys_str:
            return [
                k.strip().replace('"', '').replace("'", "") 
                for k in api_keys_str.split(",") 
                if k.strip()
            ]
        else:
            # Se não houver vírgula, limpa e retorna como chave única
            return [api_keys_str.strip().replace('"', '').replace("'", "")]
            
    return []


def analisar_relato(pistas: list, localizacao: str, relato_adicional: str) -> str:
    """
    Agrupa os dados do formulário e tenta processar com as chaves disponíveis.
    Caso a chave atual falhe (por limite de cota ou rede), o sistema tenta a próxima.
    """
    chaves_disponiveis = obter_chaves_api()
    if not chaves_disponiveis:
        raise ValueError("Nenhuma chave de API do Gemini foi configurada no servidor.")
    
    # Embaralha as chaves em cada requisição para não gastar sempre a primeira chave
    random.shuffle(chaves_disponiveis)
    
    lista_pistas = ", ".join(pistas)
    
    prompt = f"""
    DADOS COLETADOS PELO CIVIL NO LOCAL:
    - Localização do Incidente: {localizacao}
    - Pistas e Evidências Encontradas: {lista_pistas}
    - Depoimento/Relato Adicional: {relato_adicional}
    
    Com base nas suas regras de investigação da Ordo Realitas, analise o caso detalhadamente.
    Retorne APENAS o JSON conforme o esquema definido, sem blocos de código markdown adicionais.
    """
    
    erros_acumulados = []
    
    # Tenta realizar a requisição para cada chave de API disponível
    for index, key in enumerate(chaves_disponiveis):
        try:
            # Cria um cliente temporário para a chave atual da tentativa
            client = genai.Client(api_key=key)
            
            response = client.models.generate_content(
                model="gemini-3.5-flash",  
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ENTIDADE_SCHEMA,
                    temperature=0.7
                )
            )
            # Retorna o texto da resposta se bem-sucedido, encerrando o loop
            return response.text
            
        except errors.APIError as api_err:
            # Captura erros específicos do Gemini (Ex: limites de requisição 429)
            erro_msg = f"Chave {index+1} falhou (APIError {api_err.code}): {api_err.message}"
            print(f"[Aviso de Sistema - Ordo Realitas] {erro_msg}")
            erros_acumulados.append(erro_msg)
            
        except Exception as e:
            # Captura outros tipos de exceções (ex: problemas temporários de conexão)
            erro_msg = f"Chave {index+1} falhou por erro genérico: {str(e)}"
            print(f"[Aviso de Sistema - Ordo Realitas] {erro_msg}")
            erros_acumulados.append(erro_msg)
            
    # Caso todas as chaves tenham falhado, lança um erro com o histórico de problemas
    mensagem_consolidade = " | ".join(erros_acumulados)
    raise RuntimeError(f"Todas as chaves de API falharam ao processar o relato: {mensagem_consolidade}")


@app.route("/")
def root():
    return jsonify({
        "status": "success",
        "message": "API de Investigação da Ordo Realitas operacional",
        "version": "1.0"
    }), 200


@app.route("/investigar", methods=["POST"])
def investigar():
    data = request.get_json()
    
    if not data or "pistas" not in data or "localizacao" not in data:
        return jsonify({
            "status": "error",
            "message": "Dados insuficientes. Garanta o envio de 'pistas', 'localizacao' e 'relato_adicional'."
        }), 400
    
    pistas = data.get("pistas", [])
    localizacao = data.get("localizacao", "").strip()
    relato_adicional = data.get("relato_adicional", "").strip()
    
    if not isinstance(pistas, list) or len(pistas) < 2:
        return jsonify({
            "status": "error",
            "message": "A Ordo Realitas precisa de no mínimo 2 pistas para cruzar dados."
        }), 400
        
    if not localizacao:
        return jsonify({
            "status": "error",
            "message": "Defina a localização do incidente para o mapeamento."
        }), 400
    
    try:
        # Chama a função que agora possui o fallback e rotação de chaves
        analise_json_string = analisar_relato(pistas, localizacao, relato_adicional)
        analise_estruturada = json.loads(analise_json_string)
        
        if analise_estruturada.get("nome_da_entidade") == "ERRO_CASO_REJEITADO_PELO_VERISSIMO":
            return jsonify({
                "status": "error",
                "message": "⚠️ ERRO_CASO_REJEITADO: O Veríssimo arquivou este caso. A descrição não corresponde a uma ameaça paranormal legítima."
            }), 400
        
        return jsonify({
            "status": "success",
            "pistas_enviadas": pistas,
            "localizacao_enviada": localizacao,
            "dados_entidade": analise_estruturada
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erro durante a análise paranormal: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)