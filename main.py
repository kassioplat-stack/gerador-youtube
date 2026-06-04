import os, json, time, zipfile, requests, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)

CLAUDE_KEY     = os.environ.get("CLAUDE_API_KEY", "")
LEONARDO_KEY   = os.environ.get("LEONARDO_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

sessions = {}
HISTORICO_FILE = "historico.json"

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r") as f:
            return json.load(f)
    return {"videos": []}

def salvar_historico(titulo, animais):
    h = carregar_historico()
    h["videos"].append({"titulo": titulo, "data": datetime.now().isoformat(), "animais": animais})
    with open(HISTORICO_FILE, "w") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

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

ESTILOS = {
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

DURACOES = {"30": 30, "50": 50, "60": 60, "90": 90, "90m": 90}
PALAVRAS  = {"30": 65, "50": 108, "60": 130, "90": 195, "90m": 325}

def calc_frases(dur, nh):
    # Numero de frases por historia baseado na duracao
    # ~2.5 palavras/segundo, ~8 palavras por frase = ~3s por frase em media
    d = DURACOES.get(str(dur), 60)
    total = max(round(d / 3), nh * 4 + 4)
    if nh == 1:
        return {"caso1": round(total*0.70), "caso2": 0, "caso3": 0, "final": round(total*0.30)}
    elif nh == 2:
        return {"caso1": round(total*0.40), "caso2": round(total*0.40), "caso3": 0, "final": round(total*0.20)}
    else:
        return {"caso1": round(total*0.25), "caso2": round(total*0.20), "caso3": round(total*0.25), "final": round(total*0.30)}

def build_system(modelo, nh, dist, total_palavras):
    restricao = animais_recentes()
    restr = "Animais usados nos ultimos 7 dias - NAO repita: " + ", ".join(restricao) + "." if restricao else "Sem restricao de animais."

    if modelo == "psicologia":
        ctx = (
            "Voce cria roteiros virais de psicologia humana para YouTube. "
            "Os casos sao comportamentos humanos em escalada: comum, surpreendente, perturbador. "
            "Narracao em segunda pessoa direta: Voce faz isso, Voce ja percebeu. "
            "Prompts mostram HUMANOS em situacoes cotidianas reconheciveis."
        )
    elif modelo == "fatos":
        ctx = (
            "Voce cria roteiros virais de ciencia para YouTube. "
            "Os casos contradizem crencas populares: surpreendente, chocante, muda tudo. "
            "A narracao comeca contradizendo uma crenca forte. "
            "Prompts mostram ciencia, natureza, descobertas."
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
        "  \"caso1\": {\"nome\":\"string\",\"animal\":\"string\",\"nivel\":\"Interessante\",\"apresentacao\":\"string\",\"tensao\":\"string\",\"escalada\":\"string\",\"twist\":\"string\"},\n"
        "  \"caso2\": {\"nome\":\"string\",\"animal\":\"string\",\"nivel\":\"Surpreendente\",\"apresentacao\":\"string\",\"tensao\":\"string\",\"escalada\":\"string\",\"twist\":\"string\"},\n"
        "  \"caso3\": {\"nome\":\"string\",\"animal\":\"string\",\"nivel\":\"Chocante\",\"apresentacao\":\"string\",\"tensao\":\"string\",\"escalada\":\"string\",\"twist\":\"string\"},\n"
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

        "=== PSICOLOGIA DO ROTEIRO — ALMA DO VIDEO ===\n\n"

        "EMOCAO-ANCORA:\n"
        "Defina UMA emocao que conecta TODAS as historias ao espectador de forma pessoal.\n"
        "Nao e a emocao DO animal — e a emocao que o ESPECTADOR vai sentir ao se ver no animal.\n"
        "Exemplos poderosos:\n"
        "- Reconhecimento culpado: o espectador se ve no comportamento e nao gosta do que ve\n"
        "- Admiracao perturbadora: admira mas fica incomodado com o que isso diz sobre si mesmo\n"
        "- Identificacao involuntaria: nao quer se identificar mas nao consegue negar\n\n"

        "PERGUNTA INVISIVEL:\n"
        "Uma pergunta que o video responde sem nunca fazer em voz alta.\n"
        "Ela e plantada no gancho, cresce nas historias e explode no twist do caso 3.\n"
        "So e revelada indiretamente na frase final filosofica.\n"
        "Exemplos: Sera que sou tao diferente desse animal? / O que chamo de escolha e apenas instinto?\n\n"

        "=== GANCHO — PRIMEIRA IMPRESSAO ABSOLUTA ===\n\n"
        "Escolha o tipo mais poderoso para o tema:\n"
        "PROVOCACAO: afirmacao que ofende ou desafia uma crenca. Ex: Esse animal e mais honesto que a maioria das pessoas que voce conhece.\n"
        "CONTRADICAO: quebra crenca popular. Ex: O animal que voce acha romantico e na verdade o maior manipulador da natureza.\n"
        "ESPELHO HUMANO: animal faz algo humano demais. Ex: Esse animal contrata seguranças. Literalmente.\n"
        "NUMERO CURIOSO: dado especifico que para o scroll. Ex: Esse animal passou 47 dias esperando. A ciencia ficou sem explicacao.\n\n"
        "REGRAS DO GANCHO:\n"
        "- VAI DIRETO. Zero apresentacao do video. Zero contexto. A primeira palavra ja e impacto.\n"
        "- Nao explica o que vai acontecer. Joga o espectador no meio da acao.\n"
        "- Gera uma pergunta imediata na cabeca do espectador sem fazer a pergunta.\n\n"

        "=== SUB-ARCOS DE CADA HISTORIA — OBRIGATORIOS ===\n\n"
        "Cada historia tem 4 momentos DISTINTOS e PROGRESSIVOS:\n"
        "1. APRESENTACAO (equivale a 2s de video):\n"
        "   - Apresenta o personagem com UM detalhe unico e humanizante\n"
        "   - Nao generalize. Nao diga ele vive na floresta. Diga ela tem uma cicatriz no ombro direito de uma briga de 2019.\n"
        "   - O espectador deve sentir que conhece esse animal.\n\n"
        "2. TENSAO (3-4s):\n"
        "   - Algo esta errado. O espectador pressente mas nao sabe o que.\n"
        "   - Nao explique. Mostre sinais. Comportamento mudou. Algo esta diferente.\n\n"
        "3. ESCALADA (4-5s):\n"
        "   - A situacao piora. Os detalhes ficam mais especificos e perturbadores.\n"
        "   - Aqui entram os numeros: 23 dias, 340 quilos, 14 horas por dia.\n"
        "   - O espectador ja nao consegue parar de assistir.\n\n"
        "4. TWIST (2-3s):\n"
        "   - A revelacao que muda tudo. O espectador NAO esperava.\n"
        "   - Chega em rafagas curtissimas. Sem folego. Sem explicacao.\n"
        "   - Ex: Ela nao foi embora. Ficou. Por tres dias. Olhando.\n\n"

        "MICRO-PROMESSA entre caso 2 e 3 — OBRIGATORIA:\n"
        "Frase unica que promete algo ainda maior e mais perturbador.\n"
        "NUNCA use: O proximo animal e... / Agora veja... / Mas ha mais...\n"
        "Use: Mas nenhum deles chegou perto do que esse terceiro fez. / O ultimo caso perturbou os pesquisadores de Harvard.\n\n"

        "=== FILOSOFIA DE NARRACAO — LEI ABSOLUTA ===\n\n"
        "A narracao e um roteiro de filme. Nao e um documentario. Nao e uma lista de fatos.\n"
        "E uma historia UNICA que respira, acelera, para, surpreende e termina.\n"
        "O espectador NAO deve sentir que esta sendo informado.\n"
        "Deve sentir que esta sendo PUXADO para dentro de algo que nao consegue parar de ouvir.\n\n"

        "REGRAS ABSOLUTAS DA NARRACAO:\n"
        "1. FRASES COMPLETAS: cada frase tem sujeito, verbo e sentido completo. NUNCA frase cortada.\n"
        "2. NOME DO ANIMAL: cite o nome nas primeiras frases de cada historia. Nunca so ele ou ela sem apresentar antes.\n"
        "3. DETALHES ESPECIFICOS: nunca muito tempo — use 47 dias. Nunca ficou triste — use parou de comer por 11 dias.\n"
        "4. RITMO CINEMATOGRAFICO: alterne frases curtas de impacto (3-6 palavras) com frases medias descritivas (10-16 palavras).\n"
        "5. CONECTORES NATURAIS: Mas o que ninguem esperava era... / E entao algo impossivel aconteceu. / Isso sozinho ja seria incrivel. Mas espera.\n"
        "6. TRANSICOES ORGANICAS entre historias: NUNCA O proximo animal e... Use: Mas nao e o unico. / Se isso ja te surpreendeu...\n"
        "7. VIRADAS EM RAFAGAS: o twist chega sem folego. Tres frases curtas em sequencia. Sem explicacao. Sem suavizar.\n"
        "8. COESAO TOTAL: cada frase deve fluir da anterior como se fossem uma unica conversa. Zero saltos logicos.\n"
        "9. SEM REPETICAO: nunca repita a mesma ideia em frases diferentes. Cada frase avanca a historia.\n"
        "10. PONTUACAO CORRETA: ponto final, exclamacao ou interrogacao. NUNCA termine com virgula.\n"
        "11. TOTAL: aproximadamente " + str(total_palavras) + " palavras para TODA a narracao — respeite esse limite.\n\n"

        "=== REGRAS DOS PROMPTS DE IMAGEM — CONGRUENCIA TOTAL ===\n\n"
        "PRINCIPIO FUNDAMENTAL: cada prompt e a traducao visual LITERAL da frase de narracao correspondente.\n"
        "Se a narracao diz 'ela quebrou a cerca', o prompt mostra o animal quebrando a cerca — nao olhando para o horizonte.\n"
        "Se a narracao diz '47 dias esperando', o prompt mostra o animal em postura de espera tensa — nao correndo.\n"
        "NUNCA crie uma cena generica. A cena visual deve ser impossivel de trocar com qualquer outra frase.\n\n"
        "FORMATO OBRIGATORIO de cada prompt:\n"
        "[descricao fisica unica e especifica do animal] + [ACAO EXATA descrita na narracao] + [angulo que melhor captura a emocao] + [iluminacao que reforça o tom] + [estado de movimento]\n\n"
        "CARACTERISTICAS FISICAS: defina no primeiro prompt de cada historia e repita IDENTICAMENTE em todos os outros da mesma historia.\n"
        "Ex: 'large African elephant with torn left ear, deep-set amber eyes, dusty gray skin'\n"
        "Nao mude a descricao fisica dentro da mesma historia — e o mesmo personagem em cenas diferentes.\n\n"
        "ANGULOS por emocao:\n"
        "- Apresentacao: wide shot ou over the shoulder — apresenta o ambiente e o personagem\n"
        "- Tensao: close-up no rosto ou macro em detalhe corporal — cria intimidade e desconforto\n"
        "- Escalada: angulo medio dinamico — mostra o comportamento em acao\n"
        "- Twist: extreme close-up ou angulo inusitado — destabiliza o espectador\n\n"
        "ILUMINACAO por momento:\n"
        "- Apresentacao e tensao inicial: soft natural light ou golden hour — conforto falso\n"
        "- Escalada: dramatic shadows ou single spotlight — algo escuro esta acontecendo\n"
        "- Twist e final: blue hour ou high contrast — revelacao perturbadora\n\n"
        "MOVIMENTO:\n"
        "- mid-motion: quando a acao esta acontecendo agora\n"
        "- frozen in the moment: para revelaçoes, twists, momentos de choque\n"
        "- slow motion blur: para emocao intensa, fim de historia\n\n"
        "PROIBIDO em qualquer prompt:\n"
        "- cinematic, realistic, documentary, photographic (o estilo e adicionado automaticamente)\n"
        "- 'an animal' ou pronomes sem referencia — sempre o nome especifico\n"
        "- cenas genericas que poderiam ser de qualquer historia\n"
        "- acoes que contradizem o que a narracao descreve\n\n"

        "PERGUNTA DIVISORA — DIVIDE OPINIOES E GERA COMENTARIOS:\n"
        "Pessoal, direta, sem resposta obvia. Divide o publico em dois lados.\n"
        "Ex: Voce acha que isso e instinto — ou e escolha? / Isso te faz ver os animais diferente. Ou as pessoas?\n\n"

        + struct + "\n\n"
        "Responda SOMENTE em JSON valido sem markdown:\n"
        + json_template
    )

def chamar_claude(system, user_msg, max_tokens=6000, modelo="claude-sonnet-4-5-20250929"):
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
            text = re.sub(r',(\s*[}\]])', r'', text)
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
                json={"prompt": prompt + ", " + sufixo, "modelId": "7b592283-e8a7-4c5a-9ba6-d18c31f258b9",
                      "width": dims["width"], "height": dims["height"], "num_images": 1, "guidance_scale": 10,
                      "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text"},
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
                json={'text': narracao_txt, 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.8}},
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
    nh = int(data.get('historias', 3))
    duracao = str(data.get('duracao', '50'))
    dist = calc_frases(duracao, nh)
    total_palavras = PALAVRAS.get(duracao, 130)
    duracao_s = {"30":30,"50":50,"60":60,"90":90,"90m":90}.get(duracao, 60)
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
        duracao_s = {"30":30,"50":50,"60":60,"90":90,"90m":90}.get(duracao, 60)
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
    data = request.json
    print(f"NARRACAO REQUEST keys={list(data.keys())}")
    # Aceita narracao_completa (novo fluxo) ou monta das partes (legado)
    narracao_txt = data.get('narracao_completa', '').strip()
    if not narracao_txt:
        partes = [data.get('gancho',''), data.get('narracao_custom',''), data.get('frase_final',''), data.get('pergunta_divisora','')]
        narracao_txt = ' '.join(p for p in partes if p)
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
    data = request.json
    estilo = data.get('estilo', 'stylized_game')
    formato = data.get('formato', '9:16')
    prompts_custom = data.get('prompts_custom', [])
    narracao_custom = data.get('narracao_custom', '')
    narracao_session_id = data.get('narracao_session_id')

    narracao_txt = narracao_custom if narracao_custom else ' '.join(filter(None, [
        data.get('gancho', ''),
        *data.get('narracao_caso1', []),
        *data.get('narracao_caso2', []),
        data.get('micro_promessa', ''),
        *data.get('narracao_caso3', []),
        *data.get('narracao_final', []),
        data.get('frase_final', ''),
        data.get('pergunta_divisora', '')
    ]))

    prompts = prompts_custom if prompts_custom else (
        data.get('caso1', {}).get('prompts', []) +
        data.get('caso2', {}).get('prompts', []) +
        data.get('caso3', {}).get('prompts', []) +
        data.get('prompts_final', [])
    )

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

        # Se não tem narração, gera nova
        if not audio_data:
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
    return send_file(f, as_attachment=True, download_name='video_youtube.zip')

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
    try:
        text = chamar_claude(tipos_map.get(tipo, ''), f"Titulo: {titulo}", max_tokens=500, modelo="claude-haiku-4-5-20251001")
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/clonar', methods=['POST'])
def clonar():
    data = request.json
    transcricao = data.get('transcricao', '')
    titulo = data.get('titulo', '')
    obs = data.get('obs', '')
    system = "Analise a transcricao e clone a estrutura narrativa com o novo tema. Identifique o modelo (animais/psicologia/fatos). Retorne JSON no formato padrao com campo modelo_identificado."
    user_msg = f"Transcricao:\n{transcricao}\n\nNovo titulo: {titulo}\nObservacoes: {obs}"
    try:
        text = chamar_claude(system, user_msg)
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


@app.route('/gerar-prompts', methods=['POST'])
def gerar_prompts():
    data = request.json
    script = data.get('script', '')
    system = (
        "Voce e um diretor de arte especialista em videos curtos virais do YouTube."
        " Recebera um script de narracao e deve identificar os MOMENTOS NARRATIVOS."
        " Um momento nao e uma frase gramatical. E um bloco de significado narrativo."
        " Frases curtissimas em sequencia como Ela nao foi embora. Ficou. Por tres dias."
        " formam UM unico momento — cena do animal esperando."
        " Para cada momento gere um prompt de imagem que traduz LITERALMENTE aquele momento visual."
        " O numero de prompts deve ser o numero natural de momentos no script."
        " Para 60s espera-se entre 15 e 30 momentos."
        " FORMATO: descricao fisica unica do animal mais acao exata do momento mais angulo mais iluminacao mais movimento."
        " Defina as caracteristicas fisicas do animal no primeiro prompt e repita em todos os outros desse animal."
        " Angulos: wide shot para apresentacao, close-up para tensao, extreme close-up para twist."
        " Iluminacao: golden hour no inicio, dramatic shadows na escalada, blue hour na revelacao."
        " Movimento: mid-motion para acao, frozen in the moment para choque, slow motion blur para emocao."
        " PROIBIDO: cinematic, realistic, documentary, photographic, an animal."
        " Sempre use o nome especifico do animal."
        " Retorne JSON sem markdown: {\"prompts\": [\"prompt1\", \"prompt2\"]}"
    )
    user_msg = "Script:\n\n" + script + "\n\nGere os prompts identificando os momentos narrativos."
    try:
        text = chamar_claude(system, user_msg, max_tokens=4000, modelo="claude-sonnet-4-5-20250929")
        text = re.sub(r"```json|```", "", text).strip()
        d = json.loads(text)
        prompts = d.get('prompts', [])
        return jsonify({'prompts': prompts, 'total': len(prompts)})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
