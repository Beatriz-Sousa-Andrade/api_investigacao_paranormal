import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv

from config import ENTIDADE_SCHEMA, SYSTEM_INSTRUCTION


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

app = Flask(__name__)
CORS(app)


def analisar_relato(pistas: list, localizacao: str, relato_adicional: str) -> str:
    """
    Agrupa os dados do formulário e envia o cenário completo para o Gemini.
    Retorna a análise estruturada em JSON.
    """
    # Une as pistas numa única string explicativa para o modelo
    lista_pistas = ", ".join(pistas)
    
    prompt = f"""
    DADOS COLETADOS PELO CIVIL NO LOCAL:
    - Localização do Incidente: {localizacao}
    - Pistas e Evidências Encontradas: {lista_pistas}
    - Depoimento/Relato Adicional: {relato_adicional}
    
    Com base nas suas regras de investigação da Ordo Realitas, analise o caso detalhadamente.
    Retorne APENAS o JSON conforme o esquema definido, sem blocos de código markdown adicionais.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",  
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ENTIDADE_SCHEMA,
            temperature=0.7
        )
    )
    return response.text


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
    
    # Validação 1: Verifica o payload estruturado enviado pelo script.js
    if not data or "pistas" not in data or "localizacao" not in data:
        return jsonify({
            "status": "error",
            "message": "Dados insuficientes. Garanta o envio de 'pistas', 'localizacao' e 'relato_adicional'."
        }), 400
    
    pistas = data.get("pistas", [])
    localizacao = data.get("localizacao", "").strip()
    relato_adicional = data.get("relato_adicional", "").strip()
    
    # Validação 2: Mínimo de pistas idêntico ao validador do frontend
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
        # Chama o Gemini passando a estrutura de dados tática
        analise_json_string = analisar_relato(pistas, localizacao, relato_adicional)
        analise_estruturada = json.loads(analise_json_string)
        
        # Verifica se a IA rejeitou o caso (Regra de segurança do config.py)
        if analise_estruturada.get("nome_da_entidade") == "ERRO_CASO_REJEITADO_PELO_VERISSIMO":
            return jsonify({
                "status": "error",
                "message": "⚠️ ERRO_CASO_REJEITADO: O Veríssimo arquivou este caso. A descrição não corresponde a uma ameaça paranormal legítima."
            }), 400
        
        # SUCESSO: Retorna o objeto com a chave exata que o script.js espera ('dados_entidade')
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