import os, json, time, zipfile, requests, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)

CLAUDE_KEY     = os.environ.get("CLAUDE_API_KEY", "")
LEONARDO_KEY   = os.environ.get("LEONARDO_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

sessions = {}

def limpar_sessions_antigas():
    agora = time.time()
    para_remover = [k for k in sessions if agora - float(k) > 7200]
    for k in para_remover:
        sessions.pop(k, None)

HISTORICO_FILE = "historico.json"

_historico_cache = None

def carregar_historico():
    global _historico_cache
    if _historico_cache is None:
        if os.path.exists(HISTORICO_FILE):
            try:
                with open(HISTORICO_FILE, "r") as f:
                    _historico_cache = json.load(f)
            except:
                _historico_cache = {"videos": []}
        else:
            _historico_cache = {"videos": []}
    return _historico_cache

def salvar_historico(titulo, animais):
    h = carregar_historico()
    h["videos"].append({"titulo": titulo, "data": datetime.now().isoformat(), "animais": animais})
    try:
        with open(HISTORICO_FILE, "w") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except:
        pass

def animais_recentes():
    h = carregar_historico()
    sete_dias = datetime.now() - timedelta(days=7)
    recentes = []
    for v in h["videos"]:
        try:
            if datetime.fromisoformat(v["data"]) > sete_dias:
                recentes.extend(v["animais"])
        except:
            pass
    return recentes

MODELOS_LEONARDO = {
    "stylized_game":     "7b592283-e8a7-4c5a-9ba6-d18c31f258b9",  # Leonardo Creative
    "hyperrealistic":    "aa77f04e-3eec-4034-9c07-d0f619684628",  # Leonardo Kino XL
    "cinematic_dark":    "aa77f04e-3eec-4034-9c07-d0f619684628",  # Leonardo Kino XL
    "oil_painting":      "7b592283-e8a7-4c5a-9ba6-d18c31f258b9",  # Leonardo Creative
    "anime":             "e316348f-7773-490e-adcd-46757c738eb9",  # Anime XL
    "watercolor":        "7b592283-e8a7-4c5a-9ba6-d18c31f258b9",  # Leonardo Creative
}

ESTILOS = {
    "mente": "3D render, blue matte rubber character, genderless faceless smooth blue figure, white absolute background, single metaphor object, centered composition, studio lighting, high contrast, minimalist, no text, no other characters, photorealistic 3D, blender render style, clean shadows",
    "stylized_game": "stylized game character art, non-realistic, vibrant colors, bold outlines, 9:16 vertical",
    "cinematic_doc": "cinematic wildlife documentary, hyper realistic, dramatic lighting, 9:16 vertical",
    "anime": "anime style illustration, vibrant colors, emotional scene, studio ghibli inspired, 9:16 vertical",
    "dark_fantasy": "dark fantasy illustration, epic composition, moody atmosphere, highly detailed, 9:16 vertical",
    "feature_film": "semi-realistic feature film illustration, cinematic color grading, volumetric lighting, 9:16 vertical",
    "macro_nature": "ultra macro nature photography, extreme detail, bokeh background, National Geographic style, 9:16 vertical",
    "anime_moderno": "modern anime illustration style, clean bold outlines, vibrant saturated colors, natural warm lighting, 9:16 vertical",
    "cartoon_flat": "flat design cartoon illustration, clean vector art, bold outlines, solid vibrant colors, cute animal character, 2D animation style, no shadows, 9:16 vertical"
}

FORMATOS = {
    "9:16": {"width": 768, "height": 1344},
    "16:9": {"width": 1344, "height": 768},
    "1:1":  {"width": 1024, "height": 1024}
}

DURACOES = {"40": 40, "60": 60, "90": 90, "120": 120, "180": 180, "240": 240, "300": 300}
PALAVRAS  = {"40": 88, "60": 130, "90": 195, "120": 260, "180": 390, "240": 520, "300": 650}

def calc_frases(dur, nh):
    # Numero de frases por historia baseado na duracao
    # ~2.5 palavras/segundo, ~5 palavras por frase curta = ~2s por frase
    # Mistura frases curtas de impacto (2s) e medias descritivas (3s)
    d = DURACOES.get(str(dur), 60)
    total = max(round(d / 2), nh * 6 + 6)
    if nh == 1:
        return {"caso1": round(total*0.70), "caso2": 0, "caso3": 0, "final": round(total*0.30)}
    elif nh == 2:
        return {"caso1": round(total*0.40), "caso2": round(total*0.40), "caso3": 0, "final": round(total*0.20)}
    else:
        return {"caso1": round(total*0.25), "caso2": round(total*0.20), "caso3": round(total*0.25), "final": round(total*0.30)}

def build_system(modelo, nh, dist, total_palavras):
    restricao = animais_recentes()
    restr = "Animais usados nos ultimos 7 dias - NAO repita: " + ", ".join(restricao) + "." if restricao else "Sem restricao de animais."

    if modelo == "mente":
        ctx = (
            "MISSAO DO CANAL — leia antes de escrever uma palavra:\n"
            "Revelar o mecanismo psicologico oculto por tras de comportamentos humanos.\n"
            "Nao e autoajuda. Nao e motivacao. Nao e conselho.\n"
            "E expor o que esta acontecendo embaixo — o que voce nao ve, o que sua mente faz sem te avisar.\n"
            "O espectador nao aprende algo novo. Ele RECONHECE algo que ja fazia sem saber o nome.\n"
            "Isso e mais perturbador do que qualquer fato novo.\n\n"
            "IDENTIDADE DO CANAL: autoconhecimento forcado e desconfortavel.\n"
            "O espectador termina o video sabendo algo sobre si mesmo que nao pediu para saber.\n\n"

            "BANCO DE TEMAS POR NIVEL:\n"
            "Caso 1 FAMILIAR: procrastinacao, comparacao social, necessidade de aprovacao, medo de rejeicao, "
            "autossabotagem, perfeccionismo paralisante, necessidade de controle, dificuldade de pedir ajuda.\n"
            "Caso 2 PERTURBADOR: vies de confirmacao, efeito Dunning-Kruger, projecao psicologica, "
            "disonancia cognitiva, trauma de abandono mascarado, mecanismos de defesa inconscientes, "
            "apego ansioso, gaslighting que voce mesmo faz em si.\n"
            "Caso 3 CHOCANTE E PESSOAL: o espectador percebe que faz isso agora, nessa semana, "
            "nessa relacao. Temas: como o cerebro fabrica memorias falsas para se proteger, "
            "por que voce escolhe pessoas que te machucam, como voce sabotar o que mais quer, "
            "por que voce nunca se sente suficiente independente do que conquista.\n\n"

            "REGRAS DO MODELO MENTE:\n"
            "1. SEGUNDA PESSOA DIRETA E OBRIGATORIA: Voce faz isso. Voce ja percebeu. Sua mente faz.\n"
            "2. ZERO distancia entre o espectador e o conteudo — cada caso e sobre ELE, nao sobre outros.\n"
            "3. REALISMO PSICOLOGICO: baseado em estudos reais, nomes de pesquisadores, anos, universidades.\n"
            "4. NUNCA julgue. Explique o mecanismo. O espectador se julga sozinho.\n"
            "5. Prompts de imagem mostram HUMANOS em situacoes cotidianas reconheciveis — nao animais.\n"
            "6. A emocao-ancora escala: caso1=reconhecimento leve, caso2=desconforto real, caso3=perturbacao pessoal.\n"
        )
    else:
        ctx = (
            "Voce cria roteiros virais de comportamento animal para YouTube. " + restr + "\n"
            "BANCO DE ANIMAIS:\n"
            "Caso 1 FAMILIAR: elefante africano, golfinho, cachorro, leao, gorila, urso polar, baleia jubarte, cavalo, lobo, orangotango, pinguim, tartaruga gigante.\n"
            "Caso 2 MEDIO: corvo, orca, chimpanze, lontra, hiena, falcao peregrino, polvo gigante, texugo, capivara, morcego vampiro, canguru, alce.\n"
            "Caso 3 INESPERADO — NUNCA o obvio, sempre surpreendente: vespa-esmeralda, medusa imortal Turritopsis, tardigrado, polvo mimic, formiga-cortadeira, borboleta Maculinea, louva-a-deus, lula colossal.\n"
            "REGRA ABSOLUTA: os 3 animais devem ser COMPLETAMENTE DIFERENTES entre si.\nREALISMO OBRIGATORIO:\nOs comportamentos narrados devem ser REAIS e documentados pela ciencia — pesquisas, estudos, observacoes de campo.\nSe o comportamento for real, use os fatos exatos: numeros reais, locais reais, anos reais.\nSe for um comportamento plausivel mas nao documentado, ele deve ser 100% possivel biologicamente e crivel para qualquer pessoa.\nNUNCA invente comportamentos impossíveis ou exagerados demais.\nNUNCA crie historias de animais especificos com nomes proprios inventados.\nO espectador deve terminar o video pensando: isso e real, eu acredito nisso."
        )

    if nh == 1:
        struct = (
            "ESTRUTURA 1 historia profunda com 6 sub-arcos: apresentacao, desenvolvimento, crise, escalada, twist, resolucao.\n"
            "caso1: aproximadamente " + str(dist["caso1"]) + " frases de narracao.\n"
            "narracao_final: aproximadamente " + str(dist["final"]) + " frases.\n"
            "IMPORTANTE: NAO gere prompts de imagem nessa etapa. Os prompts serao gerados separadamente."
        )
    elif nh == 2:
        struct = (
            "ESTRUTURA 2 historias em contraste: familiar vs surpreendente.\n"
            "caso1: aproximadamente " + str(dist["caso1"]) + " frases de narracao.\n"
            "caso2: aproximadamente " + str(dist["caso2"]) + " frases de narracao.\n"
            "narracao_final: aproximadamente " + str(dist["final"]) + " frases.\n"
            "IMPORTANTE: NAO gere prompts de imagem nessa etapa. Os prompts serao gerados separadamente."
        )
    else:
        struct = (
            "ESTRUTURA 3 historias em ESCALADA OBRIGATORIA de emocao e intensidade:\n"
            "caso1 INTERESSANTE: aproximadamente " + str(dist["caso1"]) + " frases de narracao — animal familiar, historia que cria vinculo emocional.\n"
            "caso2 SURPREENDENTE: aproximadamente " + str(dist["caso2"]) + " frases de narracao — animal medio, historia mais intensa e inesperada.\n"
            "caso3 CHOCANTE: aproximadamente " + str(dist["caso3"]) + " frases de narracao — animal inesperado, historia que perturba e choca.\n"
            "narracao_final: aproximadamente " + str(dist["final"]) + " frases — ultima frase deve ser filosofica e lenta.\n"
            "IMPORTANTE: NAO gere prompts de imagem nessa etapa. Os prompts serao gerados separadamente com base na narracao aprovada."
        )

    json_template = (
        "{\n"
        "  \"pergunta_invisivel\": \"string — pergunta que o video responde sem dizer em voz alta\",\n"
        "  \"emocao_ancora\": \"string — emocao central que conecta tudo ao espectador\",\n"
        "  \"tipo_gancho\": \"PROVOCACAO | CONTRADICAO | ESPELHO HUMANO | NUMERO CURIOSO\",\n"
        "  \"gancho_principal\": \"string — primeira frase do video, vai direto sem apresentacao\",\n"
        "  \"gancho_opcoes\": [\"variacao2\",\"variacao3\",\"variacao4\"],\n"
        "  \"caso1\": {\"nome\":\"string\",\"animal\":\"string\",\"nivel\":\"Interessante\",\"captura\":\"string\",\"tensao\":\"string\",\"escalada\":\"string\",\"twist\":\"string\"},\n"
        "  \"caso2\": {\"nome\":\"string\",\"animal\":\"string\",\"nivel\":\"Surpreendente\",\"captura\":\"string\",\"tensao\":\"string\",\"escalada\":\"string\",\"twist\":\"string\"},\n"
        "  \"caso3\": {\"nome\":\"string\",\"animal\":\"string\",\"nivel\":\"Chocante\",\"captura\":\"string\",\"tensao\":\"string\",\"escalada\":\"string\",\"twist\":\"string\"},\n"
        "  \"micro_promessa\": \"string — frase entre caso 2 e 3 que promete algo maior, NUNCA transicao mecanica\",\n"
        "  \"narracao_caso1\": [\"" + str(dist["caso1"]) + " frases em portugues\"],\n"
        "  \"narracao_caso2\": [\"" + str(dist["caso2"]) + " frases em portugues\"],\n"
        "  \"narracao_caso3\": [\"" + str(dist["caso3"]) + " frases em portugues\"],\n"
        "  \"narracao_final\": [\"" + str(dist["final"]) + " frases em portugues\"],\n"
        "  \"frase_final_principal\": \"string filosofica lenta e profunda\",\n"
        "  \"frase_final_opcoes\": [\"op2\",\"op3\",\"op4\"],\n"
        "  \"pergunta_divisora_principal\": \"string — divide opinioes sem resposta obvia\",\n"
        "  \"pergunta_divisora_opcoes\": [\"op2\",\"op3\",\"op4\"]\n"
        "}"
    )

    return (
        ctx + "\n\n"

        "=== PSICOLOGIA DO ROTEIRO — MAQUINA DE RETENCAO ===\n\n"

        "EMOCAO-ANCORA:\n"
        "Defina UMA emocao que escala a cada historia e se torna pessoal no caso 3.\n"
        "Caso 1: o espectador sente curiosidade sobre o animal.\n"
        "Caso 2: o espectador se incomoda porque reconhece o comportamento em humanos.\n"
        "Caso 3: o espectador percebe que faz isso — e nao gosta.\n"
        "A emocao-ancora escala de CURIOSIDADE para RECONHECIMENTO para PERTURBACAO PESSOAL.\n"
        "Exemplos: Reconhecimento culpado / Admiracao perturbadora / Identificacao involuntaria.\n\n"

        "DIVIDA EMOCIONAL — OBRIGATORIA:\n"
        "O gancho cria uma divida que o espectador so paga assistindo ate o fim.\n"
        "Nao e curiosidade vaga. E uma promessa especifica e pessoal.\n"
        "A divida e plantada no gancho e cobrada na frase final + pergunta divisora.\n"
        "Ex: 'No final voce vai entender por que faz exatamente o que esse animal faz. E nao vai gostar.'\n"
        "A pergunta invisivel que o video responde sem nunca fazer em voz alta deve ser PESSOAL:\n"
        "Nao: 'Esse animal e incrivel?' — Sim: 'Eu sou diferente desse animal?' / 'O que chamo de escolha e apenas instinto?'\n\n"

        "=== GANCHO — OS 5 PRIMEIROS SEGUNDOS SEQUESTRAM A ATENCAO ===\n\n"
        "O gancho nao apresenta o video. Ele JOGA o espectador no meio da acao com uma divida emocional.\n"
        "REGRA ABSOLUTA: a primeira frase ja e o impacto maximo. Zero introducao. Zero contexto.\n\n"
        "5 tipos — escolha o mais poderoso para o tema:\n"
        "1. PROVOCACAO: afirmacao que desafia crenca. Ex: Esse animal e mais honesto que a maioria das pessoas que voce conhece.\n"
        "2. CONTRADICAO: quebra crenca popular. Ex: O animal que voce acha romantico e o maior manipulador da natureza.\n"
        "3. ESPELHO HUMANO: animal faz algo humano demais. Ex: Esse animal contrata seguranças. Literalmente.\n"
        "4. NUMERO CURIOSO: dado especifico absurdo. Ex: Esse animal passou 47 dias esperando. A ciencia ficou sem explicacao.\n"
        "5. PROMESSA SUSPENSA: promete revelacao pessoal perturbadora. Ex: O que esse animal faz nos proximos 3 minutos vai te fazer questionar uma decisao que voce tomou essa semana.\n\n"
        "REGRAS DO GANCHO:\n"
        "- Primeira palavra ja e impacto. NUNCA comece com Hoje, Voce sabia, Existe um animal.\n"
        "- Nao explica o que vai acontecer. Cria uma pergunta que o espectador precisa responder.\n"
        "- Os primeiros 5 segundos determinam 80% da retencao. Trate como o momento mais importante do video.\n\n"

        "=== SUB-ARCOS DE CADA HISTORIA — MAQUINA SEM PAUSA ===\n\n"
        "ELIMINE a apresentacao como momento separado. O animal e apresentado JA EM CONFLITO.\n"
        "O espectador aprende quem e o animal enquanto ja esta preso na tensao.\n\n"
        "Cada historia tem 4 momentos SEM RESPIRO entre eles:\n"
        "1. CAPTURA (1-2s) — animal apresentado ja em situacao de conflito ou comportamento perturbador:\n"
        "   - NAO: 'O elefante africano vive nas savanas.' SIM: 'Essa elefanta parou de andar ha 23 dias. Os pesquisadores nao entendiam por que.'\n"
        "   - O detalhe fisico unico do animal aparece aqui — integrado ao conflito, nao separado.\n\n"
        "2. TENSAO (2-3s) — algo esta errado, sinais especificos sem explicacao:\n"
        "   - Nao explique. Mostre comportamento concreto. Numeros. Detalhes fisicos.\n"
        "   - MINI-PROMESSA OBRIGATORIA no final da tensao: 'E entao veio o detalhe que ninguem conseguia explicar.'\n\n"
        "3. ESCALADA (3-4s) — detalhes mais especificos e perturbadores, stakes pessoais aumentam:\n"
        "   - Numeros exatos: 23 dias, 340 quilos, 14 horas por dia.\n"
        "   - Conecte ao espectador: o que esse comportamento diz sobre nos?\n"
        "   - PATTERN INTERRUPT obrigatorio: dado absurdo ou virada de perspectiva que contradiz o que acabou de ser dito.\n\n"
        "4. TWIST (2s) — revelacao em rafagas curtissimas que muda tudo:\n"
        "   - Tres frases curtas. Sem explicacao. Sem suavizar. Sem folego.\n"
        "   - Ex: Ela nao foi embora. Ficou. Por tres dias. Olhando.\n"
        "   - O twist implica algo sobre o espectador — nao so sobre o animal.\n\n"

        "TRANSICAO ENTRE HISTORIAS — CORTE ABRUPTO COM MINI-PROMESSA:\n"
        "NUNCA deixe o espectador respirar entre historias. Corte direto com mini-promessa.\n"
        "NUNCA use: O proximo animal e... / Agora veja... / Mas ha mais...\n"
        "USE ENTRE CASO 1 E 2: 'Mas esse comportamento nao e exclusivo dele.' / 'E nao e o unico que faz isso.'\n"
        "MICRO-PROMESSA ENTRE CASO 2 E 3 — mais intensa: 'Nenhum deles chegou perto do que o terceiro fez.' / 'O ultimo caso perturbou pesquisadores de Harvard por 3 anos.'\n\n"

        "=== FILOSOFIA DE NARRACAO — MAQUINA DE RETENCAO ===\n\n"
        "A narracao e um roteiro de thriller. Cada frase avanca. Nenhuma frase existe so para existir.\n"
        "O espectador deve sentir que se parar vai perder algo importante.\n"
        "NUNCA deixe o espectador em zona de conforto narrativo por mais de 10 segundos.\n\n"

        "REGRAS ABSOLUTAS DA NARRACAO:\n"
        "1. FRASES COMPLETAS: sujeito, verbo, sentido. NUNCA frase cortada.\n"
        "2. NOME DO ANIMAL com detalhe fisico unico nas primeiras frases. Nunca so ele ou ela.\n"
        "3. DETALHES ESPECIFICOS: 47 dias (nao muito tempo). Parou de comer por 11 dias (nao ficou triste).\n"
        "4. RITMO CINEMATOGRAFICO: alterne frases curtas de impacto (3-6 palavras) com medias (10-16 palavras).\n"
        "5. MINI-PROMESSAS INTERNAS: dentro de cada historia, plante pelo menos 1 frase que promete revelacao iminente.\n"
        "6. PATTERN INTERRUPT a cada 30s: dado absurdo, virada de perspectiva ou contradicao do que acabou de ser dito.\n"
        "7. TRANSICOES ABRUPTAS: corte direto entre historias com mini-promessa. Zero respiro.\n"
        "8. VIRADAS EM RAFAGAS: twist em 3 frases curtas. Sem explicacao. Sem suavizar.\n"
        "9. COESAO TOTAL: cada frase flui da anterior. Zero saltos logicos.\n"
        "10. SEM REPETICAO: cada frase avanca. Nunca repita a mesma ideia.\n"
        "11. PONTUACAO CORRETA: ponto final, exclamacao ou interrogacao. NUNCA virgula no final.\n"
        "12. TOTAL: aproximadamente " + str(total_palavras) + " palavras — respeite esse limite.\n"
        "13. CONGRUENCIA COM DURACAO: dimensionado EXATAMENTE para " + str(total_palavras) + " palavras.\n"
        "14. FIDELIDADE AO SCRIPT: a narracao sera gravada EXATAMENTE como escrita.\n"
        "15. ANCORAS VISUAIS: cada frase tem UM elemento visual concreto — acao fisica, postura, expressao, cor, luz.\n"
        "    Nao: 'ela sentiu o peso do silencio' → Sim: 'ela ficou parada, focinho baixo, olhos fixos no chao por 3 horas'\n"
        "16. CONSISTENCIA VISUAL: na primeira aparicao de cada animal, descreva 3-4 caracteristicas fisicas UNICAS.\n"
        "    Ex: 'leao com juba negra nas pontas, cicatriz no olho esquerdo, patas dianteiras desproporcionalmente grandes'\n"
        "17. ESCALADA DE STAKES PESSOAIS: caso1=curiosidade, caso2=reconhecimento perturbador, caso3=identificacao pessoal forcada.\n"
        "18. FRASE FINAL: NAO e filosofica lenta. E uma revelacao + impacto direto que leva ao comentario.\n\n"

        "PERGUNTA DIVISORA — GATILHO DE COMENTARIO:\n"
        "Pessoal, direta, sem resposta obvia. Divide em dois lados opostos.\n"
        "Deve ser feita enquanto o espectador ainda esta em tensao — nao depois de alivio.\n"
        "Ex: Voce acha que isso e instinto — ou e escolha? / Isso muda como voce ve esse comportamento em voce mesmo?\n\n"

        + struct + "\n\n"
        "Responda SOMENTE em JSON valido sem markdown:\n"
        + json_template
    )

def chamar_claude(system, user_msg, max_tokens=6000, modelo="claude-sonnet-4-6"):
    for tentativa in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": modelo, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user_msg}]},
                timeout=300
            )
            text = r.json()["content"][0]["text"]
            text = re.sub(r"```json|```", "", text).strip()
            # Remove trailing commas antes de fechar arrays/objetos
            text = re.sub(r',\s*([}\]])', r'\1', text)
            return text
        except Exception as e:
            if tentativa == 2:
                raise Exception(f"Claude erro: {str(e)}")
            time.sleep(5)

def leonardo_generate(prompt, formato="9:16", estilo="stylized_game"):
    sufixo = ESTILOS.get(estilo, ESTILOS["stylized_game"])
    dims = FORMATOS.get(formato, FORMATOS["9:16"])
    for tentativa in range(3):
        try:
            r = requests.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                headers={"authorization": f"Bearer {LEONARDO_KEY}", "content-type": "application/json"},
                json={"prompt": prompt + ", " + sufixo,
                      "modelId": MODELOS_LEONARDO.get(estilo, "7b592283-e8a7-4c5a-9ba6-d18c31f258b9"),
                      "width": dims["width"], "height": dims["height"], "num_images": 1,
                      "guidance_scale": 7,
                      "negative_prompt": (
                          "blurry, low quality, distorted, ugly, watermark, text, letters, words, "
                          "human hands, humans, people, multiple animals, crowded scene, "
                          "overexposed, underexposed, cartoon, anime, illustration, painting, "
                          "duplicate, deformed, mutated, extra limbs, bad anatomy"
                      )},
                timeout=40
            )
            data = r.json()
            if "sdGenerationJob" not in data:
                raise Exception(f"Leonardo erro: {data}")
            gen_id = data["sdGenerationJob"]["generationId"]
            for _ in range(50):
                time.sleep(3)
                r2 = requests.get(f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                                  headers={"authorization": f"Bearer {LEONARDO_KEY}"}, timeout=15)
                imgs = r2.json().get("generations_by_pk", {}).get("generated_images", [])
                if imgs:
                    return requests.get(imgs[0]["url"], timeout=20).content
            raise Exception("Timeout")
        except Exception as e:
            if tentativa == 2:
                raise
            time.sleep(5)

def gerar_audio(narracao_txt, session_id):
    audio_data = None
    audio_service = ''
    try:
        if ELEVENLABS_KEY:
            r = requests.post(
                f'https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}',
                headers={'xi-api-key': ELEVENLABS_KEY, 'content-type': 'application/json'},
                json={'text': narracao_txt, 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability': 0.75, 'similarity_boost': 0.75, 'style': 0.0, 'use_speaker_boost': True}},
                timeout=60
            )
            if r.status_code == 200 and len(r.content) > 100:
                audio_data = r.content
                audio_service = 'ElevenLabs'
            else:
                print(f"ElevenLabs status={r.status_code} bytes={len(r.content)}")
    except Exception as e:
        print(f"ElevenLabs erro: {e}")

    if not audio_data:
        try:
            from gtts import gTTS
            import io
            tts = gTTS(narracao_txt, lang='pt')
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            audio_data = buf.getvalue()
            audio_service = 'gTTS'
        except Exception as e:
            print(f"gTTS erro: {e}")

    if audio_data:
        sessions[session_id]['audio'] = audio_data
        try:
            with open(f'/tmp/narracao_{session_id}.mp3', 'wb') as f:
                f.write(audio_data)
        except: pass

    print(f"AUDIO: servico={audio_service} bytes={len(audio_data) if audio_data else 0}")
    return audio_data, audio_service

@app.route('/')
def index():
    try:
        with open("index.html", encoding="utf-8") as f:
            html = f.read()
        return Response(html, mimetype='text/html; charset=utf-8')
    except:
        return "<h1>Sistema carregando...</h1>", 200

@app.route('/roteiro', methods=['POST'])
def roteiro():
    data = request.json
    titulo = data.get('titulo', '').strip()
    contexto = data.get('contexto', '').strip()
    modelo = data.get('modelo', 'animais')
    nh = 3  # fixo em 3 historias — estrutura definida pelo titulo e contexto
    duracao = str(data.get('duracao', '40'))
    dist = calc_frases(duracao, nh)
    total_palavras = PALAVRAS.get(duracao, 130)
    duracao_s = {"40":40,"60":60,"90":90,"120":120,"180":180,"240":240,"300":300}.get(duracao, 60)
    system = build_system(modelo, nh, dist, total_palavras)
    chars_limite = duracao_s * 13
    user_msg = f"Titulo: {titulo}\n\nLIMITE ABSOLUTO: a narracao completa deve ter NO MAXIMO {chars_limite} caracteres totais (equivale a {duracao_s} segundos de audio a 13 chars/segundo). Respeite rigorosamente."
    if contexto:
        user_msg += f"\nContexto: {contexto}"
    try:
        text = chamar_claude(system, user_msg)
        d = json.loads(text)
        # Valida tamanho da narracao — margem de 30s
        print(f'NARRACAO GERADA: {sum(len(f) for campo in ["narracao_caso1","narracao_caso2","narracao_caso3","narracao_final"] for f in d.get(campo, []))} chars, limite={(duracao_s+30)*13} chars')
        chars_por_segundo = 13
        duracao_s = {"40":40,"60":60,"90":90,"120":120,"180":180,"240":240,"300":300}.get(duracao, 60)
        limite_chars = (duracao_s + 30) * chars_por_segundo
        campos = ['narracao_caso1','narracao_caso2','narracao_caso3','narracao_final']
        total_chars = sum(len(f) for campo in campos for f in d.get(campo, []))
        if total_chars > limite_chars:
            # Pede ao Claude para resumir mantendo a essencia
            narr_linhas = []
            for campo in campos:
                narr_linhas.extend(d.get(campo, []))
            sys_resumo = (
                "Voce e um editor de narracao para YouTube. "
                "Resuma as frases abaixo para caber em no maximo " + str(limite_chars) + " caracteres totais. "
                "REGRAS: mantenha o mesmo numero de frases. Preserve a emocao, o nome dos animais e os detalhes especificos. "
                "Torne cada frase mais concisa sem perder o impacto. "
                "Retorne apenas as frases, uma por linha, sem numeracao."
            )
            usr_resumo = "Frases (" + str(total_chars) + " chars, limite " + str(limite_chars) + "):\n" + "\n".join(narr_linhas)
            try:
                resultado = chamar_claude(sys_resumo, usr_resumo, max_tokens=2000, modelo="claude-haiku-4-5-20251001")
                novas = [f.strip() for f in resultado.strip().split("\n") if f.strip()]
                if len(novas) >= len(narr_linhas):
                    idx = 0
                    for campo in campos:
                        qtd = len(d.get(campo, []))
                        if qtd > 0:
                            d[campo] = novas[idx:idx+qtd]
                            idx += qtd
            except:
                pass
        animais = [d.get(k, {}).get('animal', '') for k in ['caso1', 'caso2', 'caso3'] if d.get(k, {}).get('animal')]
        if animais:
            salvar_historico(titulo, animais)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/narracao', methods=['POST'])
def gerar_narracao():
    limpar_sessions_antigas()
    data = request.json
    print(f"NARRACAO REQUEST keys={list(data.keys())}")
    narracao_txt = data.get('narracao_completa', '').strip()
    if not narracao_txt:
        return jsonify({'erro': 'Script vazio'}), 400
    print(f"NARRACAO TXT chars={len(narracao_txt)} preview={narracao_txt[:80]}")

    session_id = str(int(time.time()))
    sessions[session_id] = {'imagens': {}, 'prompts': [], 'audio': None}

    audio_data, audio_service = gerar_audio(narracao_txt, session_id)

    if audio_data:
        return jsonify({'ok': True, 'session_id': session_id, 'audio_url': f'/audio/{session_id}', 'servico': audio_service})
    else:
        return jsonify({'erro': 'Erro ao gerar narracao'}), 500

@app.route('/gerar', methods=['POST'])
def gerar():
    limpar_sessions_antigas()
    data = request.json
    narracao_custom = data.get('narracao_custom', '').strip()
    narracao_session_id = data.get('narracao_session_id')
    # Modelo MENTE tem estilo visual fixo — nao pode ser alterado
    modelo_conteudo = data.get('modelo', 'animais')
    if modelo_conteudo == 'mente':
        estilo = 'mente'
    else:
        estilo = data.get('estilo', 'stylized_game')
    formato = data.get('formato', '9:16')
    prompts_custom = data.get('prompts_custom', [])
    narracao_custom = data.get('narracao_custom', '')
    narracao_session_id = data.get('narracao_session_id')

    narracao_txt = narracao_custom

    prompts = prompts_custom

    session_id = str(int(time.time()))

    def stream():
        sessions[session_id] = {'imagens': {}, 'prompts': prompts, 'audio': None}
        yield 'data:' + json.dumps({'session_id': session_id}) + '\n\n'
        yield 'data:' + json.dumps({'step': 1, 'status': 'done', 'msg': 'Roteiro aprovado', 'progress': 15}) + '\n\n'

        yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': 'Gerando imagens...', 'progress': 18}) + '\n\n'
        erros = []
        for i, prompt in enumerate(prompts):
            num = str(i + 1).zfill(2)
            try:
                img = leonardo_generate(prompt, formato, estilo)
                sessions[session_id]['imagens'][i] = img
                img_path = f'/tmp/{session_id}_{i}.jpg'
                with open(img_path, 'wb') as f_img:
                    f_img.write(img)
                pct = 18 + int((i + 1) / max(len(prompts), 1) * 50)
                yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': f'Imagem {num}/{len(prompts)} ok', 'progress': pct}) + '\n\n'
            except Exception as e:
                erros.append(num)
                erro_msg = str(e)[:80]
                print(f"ERRO IMAGEM {num}: {erro_msg}")
                yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': f'Imagem {num} falhou: {erro_msg}', 'progress': 18 + int((i + 1) / max(len(prompts), 1) * 50)}) + '\n\n'

        msg_imgs = f"{len(sessions[session_id]['imagens'])}/{len(prompts)} imagens geradas"
        if erros:
            msg_imgs += f" (falharam: {', '.join(erros)})"
        yield 'data:' + json.dumps({'step': 2, 'status': 'done', 'msg': msg_imgs, 'progress': 70}) + '\n\n'
        yield 'data:' + json.dumps({'imgs_total': len(prompts)}) + '\n\n'

        # Reutiliza áudio já gerado ou gera novo
        yield 'data:' + json.dumps({'step': 3, 'status': 'active', 'msg': 'Preparando narracao...', 'progress': 72}) + '\n\n'
        audio_data = None
        audio_service = ''

        # Tenta reutilizar narração já gerada
        if narracao_session_id:
            s = sessions.get(narracao_session_id)
            if s and s.get('audio'):
                audio_data = s['audio']
                audio_service = 'reutilizado'
            else:
                audio_path = f'/tmp/narracao_{narracao_session_id}.mp3'
                if os.path.exists(audio_path):
                    with open(audio_path, 'rb') as fa:
                        audio_data = fa.read()
                    audio_service = 'disco'

        # Gera nova narracao APENAS se nao foi gerada no passo 2
        if not audio_data and narracao_session_id is None:
            audio_data, audio_service = gerar_audio(narracao_txt, session_id)

        sessions[session_id]['audio'] = audio_data
        status_audio = 'done' if audio_data else 'error'
        msg_audio = f'Narracao via {audio_service}' if audio_data else 'Erro na narracao'
        yield 'data:' + json.dumps({'step': 3, 'status': status_audio, 'msg': msg_audio, 'progress': 88}) + '\n\n'
        if audio_data:
            yield 'data:' + json.dumps({'audio_url': f'/audio/{session_id}'}) + '\n\n'

        yield 'data:' + json.dumps({'step': 4, 'status': 'active', 'msg': 'Criando ZIP...', 'progress': 92}) + '\n\n'
        try:
            zip_path = f'/tmp/video_{session_id}.zip'
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for idx, img in sessions[session_id]['imagens'].items():
                    zf.writestr(f'IMG_{str(idx + 1).zfill(2)}.jpg', img)
                # Inclui thumbnails se existirem
                for idx, img in sessions[session_id].get('thumbnails', {}).items():
                    zf.writestr(f'THUMB_{str(idx + 1).zfill(2)}.jpg', img)
                if audio_data:
                    zf.writestr('narracao.mp3', audio_data)
                rot = f"TITULO: {data.get('titulo', '')}\n\n"
                for i, n in enumerate(narracao_txt.split('.')):
                    if n.strip():
                        rot += f"{str(i + 1).zfill(2)}. {n.strip()}.\n"
                zf.writestr('roteiro.txt', rot.encode('utf-8'))
                prompts_txt = '\n\n'.join([f"IMG {str(i + 1).zfill(2)}:\n{p}" for i, p in enumerate(prompts)])
                zf.writestr('prompts.txt', prompts_txt.encode('utf-8'))
            yield 'data:' + json.dumps({'step': 4, 'status': 'done', 'msg': 'Pronto! Clique para baixar', 'progress': 100, 'zip': zip_path}) + '\n\n'
        except Exception as e:
            yield 'data:' + json.dumps({'step': 4, 'status': 'error', 'msg': f'Erro ZIP: {str(e)}'}) + '\n\n'

    return Response(stream(), mimetype='text/event-stream')

@app.route('/audio/<session_id>')
def audio(session_id):
    s = sessions.get(session_id)
    if s and s.get('audio'):
        import io
        return send_file(io.BytesIO(s['audio']), mimetype='audio/mpeg')
    audio_path = f'/tmp/narracao_{session_id}.mp3'
    if os.path.exists(audio_path):
        return send_file(audio_path, mimetype='audio/mpeg')
    return 'Nao encontrado', 404

@app.route('/imagem/<session_id>/<int:idx>')
def imagem(session_id, idx):
    import io
    s = sessions.get(session_id)
    if s and idx in s.get('imagens', {}):
        return send_file(io.BytesIO(s['imagens'][idx]), mimetype='image/jpeg')
    img_path = f'/tmp/{session_id}_{idx}.jpg'
    if os.path.exists(img_path):
        return send_file(img_path, mimetype='image/jpeg')
    return 'Nao encontrado', 404

@app.route('/download')
def download():
    f = request.args.get('file', '')
    if not f or not f.startswith('/tmp/'):
        return 'Nao encontrado', 404
    return send_file(f, as_attachment=True, download_name='projeto_youtube.zip')

@app.route('/traduzir', methods=['POST'])
def traduzir():
    prompt = request.json.get('prompt', '')
    try:
        text = chamar_claude("Traduza do ingles para o portugues de forma natural. Retorne apenas a traducao.", prompt, max_tokens=500, modelo="claude-haiku-4-5-20251001")
        return jsonify({'traducao': text})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/regenerar-imagem', methods=['POST'])
def regenerar_imagem():
    data = request.json
    session_id = data.get('session_id')
    idx = data.get('idx')
    prompt = data.get('prompt', '')
    narracao_custom = data.get('narracao_custom', '').strip()
    narracao_session_id = data.get('narracao_session_id')
    # Modelo MENTE tem estilo visual fixo — nao pode ser alterado
    modelo_conteudo = data.get('modelo', 'animais')
    if modelo_conteudo == 'mente':
        estilo = 'mente'
    else:
        estilo = data.get('estilo', 'stylized_game')
    formato = data.get('formato', '9:16')
    try:
        img = leonardo_generate(prompt, formato, estilo)
        if session_id in sessions:
            sessions[session_id]['imagens'][idx] = img
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500

@app.route('/regenerar-opcoes', methods=['POST'])
def regenerar_opcoes():
    data = request.json
    titulo = data.get('titulo', '')
    tipo = data.get('tipo', 'gancho')
    tipos_map = {
        'gancho': 'Gere 4 opcoes de gancho para o titulo. Retorne JSON: {"opcoes":["op1","op2","op3","op4"]}',
        'frase': 'Gere 4 opcoes de frase final filosofica para o titulo. Retorne JSON: {"opcoes":["op1","op2","op3","op4"]}',
        'pergunta': 'Gere 4 opcoes de pergunta divisora para o titulo. Retorne JSON: {"opcoes":["op1","op2","op3","op4"]}'
    }
    modelo_ctx = data.get('modelo', 'animais')
    system = tipos_map.get(tipo, '')
    if not system:
        return jsonify({'erro': 'Tipo invalido'}), 400
    try:
        text = chamar_claude(system, "Titulo: " + titulo + "\nModelo: " + modelo_ctx, max_tokens=500, modelo="claude-haiku-4-5-20251001")
        text = re.sub(r"```json|```", "", text).strip()
        text = re.sub(r',\s*([}\]])', r'\1', text)
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m: text = m.group()
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/gerar-prompts', methods=['POST'])
def gerar_prompts():
    limpar_sessions_antigas()
    data = request.json
    script = data.get('script', '').strip()
    duracao = str(data.get('duracao', '60'))
    print("GERAR-PROMPTS chars=" + str(len(script)) + " duracao=" + duracao)
    if not script:
        return jsonify({'erro': 'Script vazio — gere a narracao primeiro'}), 400

    # Calcula numero exato de prompts: 1 imagem a cada 3 segundos
    dur_s = DURACOES.get(duracao, 60)
    num_prompts = max(round(dur_s / 3), 8)
    print("GERAR-PROMPTS num_prompts=" + str(num_prompts))

    system = (
        "Voce e um diretor de arte especialista em videos curtos virais do YouTube."
        " Recebera um script de narracao e deve gerar EXATAMENTE " + str(num_prompts) + " prompts de imagem em ingles."
        " Distribua as cenas proporcionalmente pelo script inteiro."
        " Se precisar de mais cenas que momentos narrativos, divida momentos longos em angulos diferentes do mesmo momento."
        " O objetivo e sempre EXATAMENTE " + str(num_prompts) + " prompts — nem mais, nem menos."
        "\n\nANATOMIA OBRIGATORIA de cada prompt (nessa ordem exata):"
        "\n[ID VISUAL DO ANIMAL] + [ACAO FISICA EXATA descrita no script] + [ANGULO DE CAMERA] + [ILUMINACAO] + [MOVIMENTO] + [NEGATIVES]"
        "\n\nID VISUAL: na primeira aparicao de cada animal, extraia do script suas caracteristicas fisicas unicas"
        " (cicatriz, cor dos olhos, tamanho, detalhe anatomico especifico) e use IDENTICAMENTE em todos os prompts desse animal."
        " Ex: 'massive male lion with black-tipped mane, scar over left eye, oversized front paws, gaunt frame'"
        "\n\nACAO FISICA: traduza LITERALMENTE o que o script diz que o animal esta fazendo."
        " Nao interprete — traduza. Se o script diz 'ficou parada por 3 horas', o prompt diz 'standing completely still, unmoving'."
        " Use verbos de acao: standing, crouching, running, staring, retreating — nunca adjetivos emocionais vagos."
        "\n\nANGULOS por momento:"
        " wide shot (apresentacao e contexto), medium shot (acao em andamento),"
        " close-up (tensao e emocao), extreme close-up (twist e revelacao), aerial (escala e isolamento)."
        " shot on 85mm lens, shallow depth of field — use sempre."
        "\n\nILUMINACAO por fase:"
        " golden hour (inicio e apresentacao), soft natural light (desenvolvimento),"
        " dramatic side shadows (escalada), single spotlight (twist), cold blue hour (revelacao final)."
        "\n\nMOVIMENTO: mid-motion (acao acontecendo), frozen in the moment (choque e revelacao), slow motion blur (emocao intensa)."
        "\n\nNEGATIVES — adicione ao final de cada prompt:"
        " 'no humans, no text, no watermark, no other animals, isolated subject, no cartoon, no anime'"
        "\n\nPROIBIDO no prompt: cinematic, realistic, documentary, photographic, 'an animal'."
        " Use sempre o nome especifico do animal."
        ' Retorne JSON valido sem markdown: {"prompts": ["prompt1 completo", "prompt2 completo"]}'
    )
    # Instrucao especifica por modelo
    if data.get('modelo', 'animais') == 'mente':
        instrucao_modelo = (
            "PERSONAGEM FIXO — use em TODOS os prompts sem excecao:\n"
            "blue matte rubber 3D figure, genderless, faceless, smooth surface, "
            "no facial features except two black dot eyes, rounded head, "
            "human proportions but stylized. Este personagem E o espectador.\n\n"
            "DIRECOES VISUAIS — escolha a mais adequada para cada cena:\n"
            "1. SOMBRA REVELADORA: personagem pequeno, sombra grande e diferente revelando verdade oculta\n"
            "2. CABECA ABERTA: personagem com cabeca aberta mostrando metafora do que controla a mente\n"
            "3. DUPLO EU: duas versoes do personagem em conflito interno\n"
            "4. PSICOLOGIA SURREALISTA: personagem com objeto impossivel representando verdade psicologica\n\n"
            "ESTILO FIXO de cada prompt: white background, centered composition, single metaphor, "
            "studio lighting, high contrast, minimalist, no text\n"
            "PROIBIDO: outros personagens, animais, cenarios complexos, texto, fundo colorido\n"
        )
    else:
        instrucao_modelo = ""
    user_msg = (
        "Script de narracao:\n\n" + script +
        "\n\n" + instrucao_modelo +
        "Gere EXATAMENTE " + str(num_prompts) + " prompts em ingles. "
        "Distribua pelo script inteiro. Use angulos variados para cenas longas."
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=6000, modelo="claude-sonnet-4-6")
        print("GERAR-PROMPTS resposta chars=" + str(len(text)))
        text = re.sub(r"```json|```", "", text).strip()
        text = re.sub(r',[ \t\n]*([}\]])', r'\1', text)
        d = json.loads(text)
        prompts = d.get('prompts', [])
        print("GERAR-PROMPTS total=" + str(len(prompts)))
        return jsonify({'prompts': prompts, 'total': len(prompts)})
    except Exception as e:
        print("GERAR-PROMPTS erro=" + str(e))
        return jsonify({'erro': str(e)}), 500


@app.route('/sugerir-titulos', methods=['POST'])
def sugerir_titulos():
    data = request.json
    titulo = data.get('titulo', '').strip()
    modelo = data.get('modelo', 'animais')
    system = (
        "Voce e especialista em titulos virais para YouTube. "
        "Gere exatamente 2 titulos alternativos ao titulo fornecido. "
        "Os titulos devem ter o mesmo tema e angulo emocional mas com abordagem diferente. "
        "Devem ser igualmente virais e provocativos. "
        'Retorne JSON: {"titulos": ["titulo1", "titulo2"]}'
    )
    user_msg = "Titulo original: " + titulo + "\nModelo: " + modelo
    try:
        text = chamar_claude(system, user_msg, max_tokens=300, modelo="claude-haiku-4-5-20251001")
        text = re.sub(r"```json|```", "", text).strip()
        d = json.loads(text)
        return jsonify({'titulos': d.get('titulos', [])})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/regenerar-prompt', methods=['POST'])
def regenerar_prompt():
    data = request.json
    prompt_atual = data.get('prompt_atual', '').strip()
    idx = data.get('idx', 0)
    system = (
        "Voce e um diretor de arte especialista em videos curtos virais do YouTube."
        " Recebera um prompt de imagem e deve gerar uma variacao melhorada do mesmo."
        " A variacao deve manter o mesmo momento narrativo e o mesmo animal,"
        " mas com angulo, iluminacao ou composicao diferente."
        " Mantenha as caracteristicas fisicas do animal identicas."
        " PROIBIDO: cinematic, realistic, documentary, photographic, an animal."
        " Retorne apenas o novo prompt em ingles, sem explicacoes."
    )
    user_msg = "Prompt atual:\n" + prompt_atual + "\n\nGere uma variacao melhorada."
    try:
        text = chamar_claude(system, user_msg, max_tokens=300, modelo="claude-haiku-4-5-20251001")
        text = text.strip().strip('"')
        return jsonify({'prompt': text})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/gerar-thumbnails', methods=['POST'])
def gerar_thumbnails():
    data = request.json
    roteiro = data.get('roteiro', {})
    script = data.get('script', '')
    formato = data.get('formato', '9:16')
    narracao_custom = data.get('narracao_custom', '').strip()
    narracao_session_id = data.get('narracao_session_id')
    # Modelo MENTE tem estilo visual fixo — nao pode ser alterado
    modelo_conteudo = data.get('modelo', 'animais')
    if modelo_conteudo == 'mente':
        estilo = 'mente'
    else:
        estilo = data.get('estilo', 'stylized_game')

    # Extrai contexto do roteiro
    caso3 = roteiro.get('caso3', {})
    caso1 = roteiro.get('caso1', {})
    animal3 = caso3.get('animal', '')
    animal1 = caso1.get('animal', '')
    twist3 = caso3.get('twist', '')
    emocao = roteiro.get('emocao_ancora', '')

    system = (
        "Voce e um especialista em thumbnails virais para YouTube."
        " Gere 3 conceitos de thumbnail para o video descrito."
        " REGRAS ABSOLUTAS:"
        " 1. ZERO texto na imagem — nenhuma palavra, letra ou numero."
        " 2. Cada thumbnail tem um conceito visual e emocao gatilho diferente."
        " 3. Os prompts devem gerar imagens que param o scroll em 0.3 segundos."
        " 4. Foco em rosto, olhos ou momento de tensao maxima."
        " CONCEITOS OBRIGATORIOS:"
        " Thumbnail 1 TENSAO MAXIMA: close extremo no animal do caso 3 no momento do twist. Olhos, expressao, iluminacao dramatica. O espectador sente que algo esta errado."
        " Thumbnail 2 ESPELHO HUMANO: o animal em comportamento mais humano do video. O espectador se reconhece. Composicao central, elemento perturbador sutil."
        " Thumbnail 3 CURIOSIDADE VISUAL: cena ambigua — o espectador nao entende o que esta acontecendo. Provoca a pergunta visual que gera o clique."
        " FORMATO do prompt: [descricao fisica UNICA do animal] + [cena exata] + [angulo] + [iluminacao] + [movimento]. Em INGLES."
        " PROIBIDO: cinematic, realistic, documentary, photographic, text, words, letters."
        ' Retorne JSON: {"conceitos": [{"emocao": "nome da emocao", "conceito": "descricao do conceito visual em portugues", "prompt": "prompt em ingles"}, ...]}'
    )

    user_msg = (
        "Roteiro:\n"
        "Animal caso 1: " + animal1 + "\n"
        "Animal caso 3 (mais chocante): " + animal3 + "\n"
        "Twist do caso 3: " + twist3 + "\n"
        "Emocao ancora: " + emocao + "\n"
        "Script: " + script[:500]
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=1500, modelo="claude-sonnet-4-6")
        text = re.sub(r"```json|```", "", text).strip()
        d = json.loads(text)
        return jsonify({'conceitos': d.get('conceitos', [])})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/gerar-thumbnail-imagem', methods=['POST'])
def gerar_thumbnail_imagem():
    data = request.json
    idx = data.get('idx', 0)
    prompt = data.get('prompt', '')
    formato = data.get('formato', '9:16')
    narracao_custom = data.get('narracao_custom', '').strip()
    narracao_session_id = data.get('narracao_session_id')
    # Modelo MENTE tem estilo visual fixo — nao pode ser alterado
    modelo_conteudo = data.get('modelo', 'animais')
    if modelo_conteudo == 'mente':
        estilo = 'mente'
    else:
        estilo = data.get('estilo', 'stylized_game')
    session_id = data.get('session_id', '')

    try:
        img = leonardo_generate(prompt, formato, estilo)
        # Salva na session
        if session_id and session_id in sessions:
            if 'thumbnails' not in sessions[session_id]:
                sessions[session_id]['thumbnails'] = {}
            sessions[session_id]['thumbnails'][idx] = img
        # Salva em disco como fallback
        try:
            with open(f'/tmp/thumb_{session_id}_{idx}.jpg', 'wb') as f:
                f.write(img)
        except: pass
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500


@app.route('/thumbnail/<session_id>/<int:idx>')
def thumbnail(session_id, idx):
    import io
    s = sessions.get(session_id)
    if s and idx in s.get('thumbnails', {}):
        return send_file(io.BytesIO(s['thumbnails'][idx]), mimetype='image/jpeg')
    path = f'/tmp/thumb_{session_id}_{idx}.jpg'
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return 'Nao encontrado', 404


@app.route('/score-viral', methods=['POST'])
def score_viral():
    data = request.json
    roteiro = data.get('roteiro', {})

    gancho = roteiro.get('gancho_principal', '')
    tipo_gancho = roteiro.get('tipo_gancho', '')
    emocao = roteiro.get('emocao_ancora', '')
    pergunta_inv = roteiro.get('pergunta_invisivel', '')
    micro = roteiro.get('micro_promessa', '')
    caso1 = roteiro.get('caso1', {})
    caso2 = roteiro.get('caso2', {})
    caso3 = roteiro.get('caso3', {})
    frase_final = roteiro.get('frase_final_principal', '')
    pergunta_div = roteiro.get('pergunta_divisora_principal', '')
    narracao = ' '.join(
        roteiro.get('narracao_caso1', []) +
        roteiro.get('narracao_caso2', []) +
        roteiro.get('narracao_caso3', []) +
        roteiro.get('narracao_final', [])
    )

    system = (
        "Voce e o maior especialista em crescimento de canais faceless no YouTube em 2026."
        " Avalie o roteiro fornecido em 5 dimensoes de 0 a 20 pontos cada."
        " Seja RIGOROSO — um score acima de 80 e raro e merece. Abaixo de 50 e comum."
        " DIMENSOES:"
        " 1. FORCA DO GANCHO (0-20): vai direto sem apresentacao? gera pergunta imediata? e do tipo certo para o tema?"
        " 2. ESCALADA EMOCIONAL (0-20): caso1 menor que caso2 menor que caso3 em intensidade real? micro-promessa funciona?"
        " 3. QUALIDADE DO TWIST (0-20): e impossivel de prever? chega em rafagas curtas? muda a percepcao de tudo?"
        " 4. PERGUNTA DIVISORA (0-20): divide em dois lados reais? e pessoal o suficiente? vai gerar comentarios polarizados?"
        " 5. CONGRUENCIA NARRATIVA (0-20): pergunta invisivel esta plantada e respondida? emocao-ancora aparece nos 3 casos? fio condutor sentido sem ser dito?"
        " Para cada dimensao retorne: score (0-20) e justificativa de 1 frase."
        " Identifique o PONTO MAIS FRACO e uma SUGESTAO ESPECIFICA de melhoria."
        ' Retorne JSON: {"total": 0-100, "dimensoes": [{"nome": "string", "score": 0-20, "justificativa": "string"}], "ponto_fraco": "string", "sugestao": "string"}'
    )

    user_msg = (
        "GANCHO: " + gancho + "\n"
        "TIPO: " + tipo_gancho + "\n"
        "EMOCAO-ANCORA: " + emocao + "\n"
        "PERGUNTA INVISIVEL: " + pergunta_inv + "\n"
        "CASO1 (" + caso1.get('nivel','') + "): " + caso1.get('animal','') + " — twist: " + caso1.get('twist','') + "\n"
        "CASO2 (" + caso2.get('nivel','') + "): " + caso2.get('animal','') + " — twist: " + caso2.get('twist','') + "\n"
        "CASO3 (" + caso3.get('nivel','') + "): " + caso3.get('animal','') + " — twist: " + caso3.get('twist','') + "\n"
        "MICRO-PROMESSA: " + micro + "\n"
        "FRASE FINAL: " + frase_final + "\n"
        "PERGUNTA DIVISORA: " + pergunta_div + "\n"
        "NARRACAO (primeiros 800 chars): " + narracao[:800]
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=1000, modelo="claude-sonnet-4-6")
        text = re.sub(r"```json|```", "", text).strip()
        # Remove trailing commas
        text = re.sub(r',\s*([}\]])', r'', text)
        # Extrai apenas o primeiro JSON valido
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group()
        d = json.loads(text)
        if 'dimensoes' in d:
            d['total'] = sum(dim.get('score', 0) for dim in d['dimensoes'])
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/corrigir-dimensao', methods=['POST'])
def corrigir_dimensao():
    data = request.json
    roteiro = data.get('roteiro', {})
    dimensao = data.get('dimensao', '')
    justificativa = data.get('justificativa', '')
    sugestao = data.get('sugestao', '')

    # Mapa de dimensao para campos do roteiro
    campos_por_dimensao = {
        'FORCA DO GANCHO': 'gancho_principal, gancho_opcoes',
        'ESCALADA EMOCIONAL': 'caso3 (twist), micro_promessa',
        'QUALIDADE DO TWIST': 'caso3 (twist), narracao_caso3',
        'PERGUNTA DIVISORA': 'pergunta_divisora_principal, pergunta_divisora_opcoes',
        'CONGRUENCIA NARRATIVA': 'narracao_caso3, narracao_final, frase_final_principal',
    }
    campos = campos_por_dimensao.get(dimensao.upper(), 'campos relevantes')

    system = (
        "Voce e um especialista em roteiros virais para YouTube."
        " Recebera um roteiro completo com um problema especifico identificado."
        " Sua tarefa: corrigir APENAS os campos necessarios para resolver o problema."
        " NAO altere o que nao foi solicitado. Preserve o estilo, tom e estrutura geral."
        " Retorne JSON apenas com os campos corrigidos — nao inclua campos que nao mudaram."
        " Campos possiveis: gancho_principal, gancho_opcoes, caso3, micro_promessa,"
        " narracao_caso3, frase_final_principal, frase_final_opcoes,"
        " pergunta_divisora_principal, pergunta_divisora_opcoes, narracao_final."
        " Para caso3, retorne apenas os subcampos alterados (twist, escalada, etc)."
        " Retorne JSON valido sem markdown."
    )

    user_msg = (
        "ROTEIRO ATUAL:\n" + json.dumps(roteiro, ensure_ascii=False)[:2000] + "\n\n"
        "DIMENSAO COM PROBLEMA: " + dimensao + "\n"
        "PROBLEMA IDENTIFICADO: " + justificativa + "\n"
        "SUGESTAO DE MELHORIA: " + sugestao + "\n"
        "CAMPOS A CORRIGIR: " + campos + "\n\n"
        "Corrija apenas o necessario para resolver o problema mantendo tudo mais intacto."
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=2000, modelo="claude-sonnet-4-6")
        text = re.sub(r"```json|```", "", text).strip()
        # Remove trailing commas e texto extra apos o JSON
        text = re.sub(r',\s*([}\]])', r'', text)
        # Extrai apenas o primeiro objeto JSON valido
        import re as re2
        m = re2.search(r'\{.*\}', text, re2.DOTALL)
        if m:
            text = m.group()
        d = json.loads(text)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/gerar-contexto', methods=['POST'])
def gerar_contexto():
    data = request.json
    titulo = data.get('titulo', '').strip()
    modelo = data.get('modelo', 'animais')
    duracao = data.get('duracao', '60')
    contexto_atual = data.get('contexto_atual', '').strip()

    dur_s = DURACOES.get(str(duracao), 60)

    system = (
        "Voce e um estrategista de conteudo viral para YouTube."
        " Dado um titulo de video, gere um contexto criativo e especifico que vai guiar a criacao do roteiro."
        " O contexto deve incluir:"
        " - Angulo emocional especifico (qual emocao o video vai explorar)"
        " - Sugestao de animais ou casos especificos se relevante"
        " - Tom narrativo (perturbador, filosofico, chocante, etc)"
        " - Elemento diferenciador que vai tornar esse video unico"
        " Seja ESPECIFICO e CRIATIVO — nao generalize."
        " O contexto deve ter entre 2 e 4 frases diretas e objetivas."
        " Retorne apenas o contexto em texto, sem explicacoes adicionais."
    )

    user_msg = "Titulo: " + titulo
    user_msg += "\nModelo: " + modelo
    user_msg += "\nDuracao: " + str(dur_s) + "s"
    if contexto_atual:
        user_msg += "\nContexto atual (gere uma variacao DIFERENTE): " + contexto_atual

    try:
        text = chamar_claude(system, user_msg, max_tokens=300, modelo="claude-haiku-4-5-20251001")
        text = text.strip().strip('"')
        return jsonify({'contexto': text})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/avaliar-thumbnail', methods=['POST'])
def avaliar_thumbnail():
    data = request.json
    imagem_b64 = data.get('imagem', '')
    canal = data.get('canal', 'geral')

    if not imagem_b64:
        return jsonify({'erro': 'Imagem vazia'}), 400

    if ',' in imagem_b64:
        media_type = imagem_b64.split(';')[0].replace('data:', '')
        imagem_b64 = imagem_b64.split(',')[1]
    else:
        media_type = 'image/jpeg'

    canal_ctx = {
        'animais': 'Canal de comportamento animal — cenas cinematograficas de animais reais, estilo documental estilizado.',
        'mente': 'Canal de psicologia — personagem azul 3D neutro genderless, fundo branco absoluto, metafora visual minimalista, texto integrado bold.',
        'geral': 'Canal generico de conteudo educativo viral para YouTube.'
    }.get(canal, 'Canal generico')

    system = (
        "Voce e o maior analista de thumbnails do YouTube do mundo."
        " Ja analisou mais de 500 mil thumbnails e sabe exatamente por que uma imagem para o scroll e outra nao."
        " Analise a thumbnail com precisao cirurgica."
        " CONTEXTO DO CANAL: " + canal_ctx +
        " ENTREGUE:"
        " 1. SCORE em 4 dimensoes de 0-25 cada com justificativa especifica do que ve na imagem."
        " 2. DIAGNOSTICO: 6 analises — teste dos 0.3 segundos (o que o olho ve primeiro/segundo/terceiro),"
        " hierarquia visual (o que domina, o que compete), gatilho emocional (qual emocao e intensidade),"
        " consistencia de canal, analise do texto (amplifica ou compete), diagnostico final em 2 frases."
        " 3. CHECKLIST: 5 perguntas sim/nao que o espectador responderia em 0.3 segundos."
        " 4. TITULOS: 3 opcoes de texto curto para a thumbnail — ordenadas da mais viral para a menos viral."
        " 5. PROMPT DE CORRECAO: prompt completo em ingles para Leonardo gerar versao melhorada com texto integrado."
        " O prompt deve corrigir ESPECIFICAMENTE os problemas identificados e manter o que funciona."
        " DIMENSOES DE SCORE:"
        " 1. PARADA DE SCROLL (0-25): elemento dominante claro, contraste, ponto focal unico."
        " 2. HIERARQUIA VISUAL (0-25): caminho do olho claro, sem elementos competindo, composicao."
        " 3. GATILHO EMOCIONAL (0-25): emocao clara, intensidade, curiosidade ou choque gerado."
        " 4. CONSISTENCIA DE CANAL (0-25): identidade visual reconhecivel, estilo coerente, texto integrado."
        ' Retorne JSON: {'
        '"total": 0-100,'
        '"dimensoes": [{"nome": "string", "score": 0-25, "justificativa": "string especifica sobre a imagem"}],'
        '"diagnostico": "analise completa em paragrafos com as 6 dimensoes",'
        '"checklist": [{"pergunta": "string", "ok": true/false}],'
        '"titulos": ["titulo mais viral", "segundo", "terceiro"],'
        '"prompt_correcao": "prompt completo em ingles para Leonardo",'
        '"ponto_fraco": "dimensao mais fraca",'
        '"sugestao": "sugestao especifica e visual"}'
    )

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 2000,
                "system": system,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": imagem_b64}},
                        {"type": "text", "text": "Analise esta thumbnail seguindo todas as instrucoes. Seja especifico sobre o que ve na imagem."}
                    ]
                }]
            },
            timeout=30
        )
        resp = r.json()
        text = resp['content'][0]['text']
        text = re.sub(r"```json|```", "", text).strip()
        d = json.loads(text)
        if 'dimensoes' in d:
            d['total'] = sum(dim.get('score', 0) for dim in d['dimensoes'])
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/corrigir-dim-thumbnail', methods=['POST'])
def corrigir_dim_thumbnail():
    data = request.json
    dimensao = data.get('dimensao', '')
    justificativa = data.get('justificativa', '')
    prompt_atual = data.get('prompt_atual', '')
    canal = data.get('canal', 'geral')

    system = (
        "Voce e especialista em thumbnails virais do YouTube."
        " Recebera um prompt de imagem e um problema especifico identificado numa dimensao."
        " Sua tarefa: atualizar o prompt para corrigir ESPECIFICAMENTE aquela dimensao."
        " Mantenha tudo que ja estava bom no prompt original."
        " Retorne apenas o prompt atualizado em ingles, sem explicacoes."
    )
    user_msg = (
        "PROMPT ATUAL:\n" + prompt_atual +
        "\n\nDIMENSAO COM PROBLEMA: " + dimensao +
        "\nPROBLEMA ESPECIFICO: " + justificativa +
        "\n\nAtualize o prompt para corrigir esse problema especifico."
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=500, modelo="claude-sonnet-4-6")
        text = text.strip().strip('"')
        return jsonify({'prompt_atualizado': text})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

