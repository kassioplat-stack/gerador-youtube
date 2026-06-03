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
RITMOS   = {"lento": 3.0, "medio": 2.0, "rapido": 1.5}
PALAVRAS  = {"30": 65, "50": 108, "60": 130, "90": 195, "90m": 325}

def calc_imagens(dur, rit, nh):
    d = DURACOES.get(str(dur), 60)
    r = RITMOS.get(rit, 2.0)
    t = max(round(d / r), nh * 3 + 3)
    if nh == 1:
        return {"caso1": round(t*0.70), "caso2": 0, "caso3": 0, "final": round(t*0.30)}
    elif nh == 2:
        return {"caso1": round(t*0.40), "caso2": round(t*0.40), "caso3": 0, "final": round(t*0.20)}
    else:
        return {"caso1": round(t*0.25), "caso2": round(t*0.20), "caso3": round(t*0.25), "final": round(t*0.30)}

def build_system(modelo, nh, dist, total_palavras):
    restricao = animais_recentes()
    restr = f"Animais usados nos ultimos 7 dias - NAO repita: {', '.join(restricao)}." if restricao else "Sem restricao de animais."

    if modelo == "psicologia":
        ctx = """Voce e especialista em roteiros virais de psicologia humana para YouTube.
Os casos sao comportamentos humanos em escalada: comum, surpreendente, perturbador.
A narracao usa segunda pessoa direta: "Voce faz isso", "Voce ja percebeu", "Isso acontece com voce".
Os prompts mostram HUMANOS em situacoes cotidianas reconheciveis."""
    elif modelo == "fatos":
        ctx = """Voce e especialista em roteiros virais de ciencia e percepcao para YouTube.
Os casos sao fatos que contradizem crencas populares: surpreendente, chocante, muda tudo.
A narracao comeca contradizendo uma crenca: "Voce acredita que X. A ciencia prova que esta errado."
Os prompts mostram: cerebros, experimentos, universo, natureza, descobertas cientificas."""
    else:
        ctx = f"""Voce e especialista em roteiros virais de comportamento animal para YouTube.
{restr}
BANCO DE ANIMAIS:
- Caso 1 familiar: Elefante africano, golfinho, cachorro, leao, gorila, urso polar, baleia jubarte, cavalo, lobo, orangotango
- Caso 2 medio: Corvo, orca, chimpanze, lontra, hiena, falcao peregrino, polvo gigante, texugo, capivara, morcego vampiro
- Caso 3 inesperado: Abelha, formiga-cortadeira, borboleta Maculinea, polvo mimic, vespa-esmeralda, louva-a-deus, medusa imortal Turritopsis"""

    if nh == 1:
        struct = f"""ESTRUTURA 1 historia profunda:
- caso1: {dist['caso1']} prompts com 6 sub-arcos expandidos: apresentacao, desenvolvimento, crise, escalada, twist, resolucao
- prompts_final: {dist['final']} prompts de revelacao filosofica
- narracao_caso1: {dist['caso1']} frases, narracao_final: {dist['final']} frases"""
    elif nh == 2:
        struct = f"""ESTRUTURA 2 historias em contraste:
- caso1: {dist['caso1']} prompts historia familiar
- caso2: {dist['caso2']} prompts historia inesperada  
- prompts_final: {dist['final']} prompts revelacao
- narracoes correspondentes para cada historia"""
    else:
        struct = f"""ESTRUTURA 3 historias em escalada obrigatoria:
- caso1: {dist['caso1']} prompts — animal FAMILIAR, nivel Interessante
- caso2: {dist['caso2']} prompts — animal MEDIO, nivel Surpreendente
- caso3: {dist['caso3']} prompts — animal INESPERADO, nivel Chocante — nunca o mais obvio
- prompts_final: {dist['final']} prompts — revelacao filosofica, ultimo prompt deve ser espelho humano
- narracoes correspondentes para cada historia"""

    return f"""{ctx}

PSICOLOGIA DO ROTEIRO — ESSENCIA OBRIGATORIA:

EMOCAO-ANCORA: Defina UMA emocao central que conecta todas as historias ao espectador.
Exemplos: "reconhecimento culpado" — o espectador se ve no animal e nao gosta.
"admiracao perturbadora" — o espectador admira mas fica incomodado.
"identificacao involuntaria" — o espectador nao quer se identificar mas se identifica.

PERGUNTA INVISIVEL: Uma pergunta que o video responde sem nunca fazer em voz alta.
Exemplos: "Sera que sou narcisista como esse animal?"
"Sera que o que chamo de amor e apenas instinto?"
O espectador deve terminar o video com essa pergunta na cabeca sem saber que ela foi plantada.

GANCHO — 4 TIPOS, escolha o mais poderoso para o tema:
1. PROVOCACAO: Afirmacao que ofende ou desafia uma crenca. "Esse animal e mais honesto que a maioria das pessoas."
2. CONTRADICAO: Quebra uma crenca popular. "O animal que voce acha romantico e na verdade o maior manipulador da natureza."
3. ESPELHO HUMANO: Mostra o animal fazendo algo humano demais. "Esse animal contrata seguranças. Literalmente."
4. NUMERO CURIOSO: Dado especifico que para o scroll. "Esse animal passou 47 dias chorando. A ciencia mediu."

SUB-ARCOS POR HISTORIA — cada historia tem 4 momentos:
- Apresentacao 2s: apresenta o personagem com um detalhe unico e humanizante
- Tensao 3-4s: algo esta errado, o espectador sente que algo vai acontecer
- Escalada 4-5s: a situacao piora, o comportamento se intensifica
- Twist 2-3s: a revelacao que muda tudo, o espectador nao esperava

MICRO-PROMESSA entre historia 2 e 3: Uma frase que promete algo ainda maior.
"Mas tem um terceiro. Esse vai te incomodar de verdade."
"E o ultimo caso? Nenhum cientista acreditou quando publicaram."

FILOSOFIA DE NARRACAO — LEI ABSOLUTA:
A narracao e um roteiro de filme. Uma historia unica que respira, acelera, para, surpreende.
Total aproximado: {total_palavras} palavras para a narracao COMPLETA.
REGRA DE TAMANHO POR FRASE — OBRIGATORIA:
Cada frase individual deve ter entre 8 e 16 palavras.
Frases de impacto podem ter 3-5 palavras. Frases descritivas ate 18 palavras.
O conjunto total deve soar completo e fluido — nunca cortado.
NUNCA escreva mais do que {total_palavras} palavras no total de toda a narracao.

REGRAS DA NARRACAO:
1. Cite o nome do animal explicitamente nas primeiras frases de cada historia
2. Use detalhes especificos — nunca "muito tempo", use "47 dias". Nunca "ficou triste", use "parou de comer por 11 dias"
3. Alterne frases curtas de impacto com frases medias descritivas
4. Conectores naturais entre frases: "Mas o que ninguem esperava era...", "E entao algo impossivel aconteceu."
5. Transicoes naturais entre historias: nunca "O proximo animal e..." — use "Mas nao e o unico." ou "Se isso ja te surpreendeu..."
6. Viradas em frases curtissimas sem folego: "Ela nao foi embora. Ficou. Por tres dias."
7. Final filosofico que desacelera: uma ou duas frases longas e profundas que ficam na cabeca

REGRAS DOS PROMPTS DE IMAGEM:
1. Cada prompt e a representacao visual EXATA da frase de narracao correspondente
2. Define caracteristicas fisicas unicas do animal no inicio de cada historia e mantem em todos os prompts
3. Formato: personagem especifico + acao exata da cena + angulo de camera + iluminacao + movimento
4. Angulos: close-up, wide shot, aerial, macro, over the shoulder
5. Iluminacao: golden hour, single spotlight, soft natural light, blue hour, dramatic shadows
6. Movimento: mid-motion, frozen in the moment, slow motion
7. NUNCA use "cinematic", "realistic", "documentary" — o estilo e adicionado pelo sistema
8. NUNCA use "an animal" — sempre o nome especifico

PERGUNTA DIVISORA — divide opinioes e gera comentarios:
Deve ser pessoal, direta, sem resposta obvia. Divide o publico em dois lados claros.
"Voce acha que isso e instinto ou escolha?"
"Isso te faz ver os animais diferente — ou as pessoas?"

{struct}

Responda SOMENTE em JSON valido sem markdown:
{{
  "pergunta_invisivel": "string — pergunta que o video responde sem dizer em voz alta",
  "emocao_ancora": "string — emocao central que conecta tudo ao espectador",
  "tipo_gancho": "PROVOCACAO | CONTRADICAO | ESPELHO HUMANO | NUMERO CURIOSO",
  "gancho_principal": "string — primeira frase do video, vai direto sem apresentacao",
  "gancho_opcoes": ["variacao 2", "variacao 3", "variacao 4"],
  "caso1": {{
    "nome": "string — nome da historia",
    "animal": "string — nome do animal",
    "nivel": "Interessante",
    "apresentacao": "string — detalhe unico e humanizante",
    "tensao": "string — algo esta errado",
    "escalada": "string — situacao se intensifica",
    "twist": "string — revelacao que muda tudo",
    "prompts": ["array de {dist['caso1']} prompts em ingles fieis a narracao"]
  }},
  "caso2": {{
    "nome": "string",
    "animal": "string",
    "nivel": "Surpreendente",
    "apresentacao": "string",
    "tensao": "string",
    "escalada": "string",
    "twist": "string",
    "prompts": ["array de {dist['caso2']} prompts em ingles"]
  }},
  "caso3": {{
    "nome": "string",
    "animal": "string",
    "nivel": "Chocante",
    "apresentacao": "string",
    "tensao": "string",
    "escalada": "string",
    "twist": "string",
    "prompts": ["array de {dist['caso3']} prompts em ingles"]
  }},
  "micro_promessa": "string — frase entre historia 2 e 3 que promete algo maior",
  "prompts_final": ["array de {dist['final']} prompts em ingles — ultimo e espelho humano"],
  "narracao_caso1": ["array de {dist['caso1']} frases em portugues — fluidas e emocionais"],
  "narracao_caso2": ["array de {dist['caso2']} frases em portugues"],
  "narracao_caso3": ["array de {dist['caso3']} frases em portugues"],
  "narracao_final": ["array de {dist['final']} frases em portugues — ultima e filosofica"],
  "frase_final_principal": "string — frase filosofica que fica na cabeca",
  "frase_final_opcoes": ["variacao 2", "variacao 3", "variacao 4"],
  "pergunta_divisora_principal": "string — divide opinioes, gera comentarios",
  "pergunta_divisora_opcoes": ["variacao 2", "variacao 3", "variacao 4"]
}}"""

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
            return re.sub(r"```json|```", "", text).strip()
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

@app.route('/')
def index():
    try:
        with open("index.html", encoding="utf-8") as f:
            html = f.read()
        return Response(html, mimetype='text/html; charset=utf-8')
    except:
        return "<h1>Sistema carregando...</h1>", 200



def validar_e_resumir_narracao(d, duracao_str):
    palavras_alvo = {"30": 65, "50": 108, "60": 130, "90": 195, "90m": 325}
    alvo = palavras_alvo.get(str(duracao_str), 130)
    margem_30s = 65  # 30 segundos = ~65 palavras extras
    limite = alvo + margem_30s
    campos = ['narracao_caso1', 'narracao_caso2', 'narracao_caso3', 'narracao_final']
    todas = []
    for campo in campos:
        todas.extend(d.get(campo, []))
    total = sum(len(f.split()) for f in todas)
    if total <= limite:
        return d
    # Resumo proporcional — encurta cada frase mantendo essência
    fator = alvo / total
    for campo in campos:
        frases = d.get(campo, [])
        novas = []
        for frase in frases:
            palavras = frase.split()
            limite_frase = max(6, int(len(palavras) * fator))
            if len(palavras) > limite_frase:
                # Corta na última pontuação dentro do limite
                cortada = ' '.join(palavras[:limite_frase])
                for sep in ['.', '?', '!', ',']:
                    idx = cortada.rfind(sep)
                    if idx > len(cortada) * 0.6:
                        cortada = cortada[:idx+1]
                        break
                novas.append(cortada)
            else:
                novas.append(frase)
        d[campo] = novas
    return d

@app.route('/roteiro', methods=['POST'])
def roteiro():
    data = request.json
    titulo = data.get('titulo', '').strip()
    contexto = data.get('contexto', '').strip()
    modelo = data.get('modelo', 'animais')
    nh = int(data.get('historias', 3))
    duracao = str(data.get('duracao', '50'))
    ritmo = data.get('ritmo', 'medio')
    dist = calc_imagens(duracao, ritmo, nh)
    total_palavras = PALAVRAS.get(duracao, 130)
    system = build_system(modelo, nh, dist, total_palavras)
    user_msg = f"Titulo: {titulo}"
    if contexto:
        user_msg += f"\nContexto: {contexto}"
    try:
        text = chamar_claude(system, user_msg)
        d = json.loads(text)
        d = validar_e_resumir_narracao(d, duracao)
        animais = [d.get(k, {}).get('animal', '') for k in ['caso1', 'caso2', 'caso3'] if d.get(k, {}).get('animal')]
        if animais:
            salvar_historico(titulo, animais)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/gerar', methods=['POST'])
def gerar():
    data = request.json
    estilo = data.get('estilo', 'stylized_game')
    formato = data.get('formato', '9:16')
    modo_teste = data.get('modo_teste', False)
    prompts_custom = data.get('prompts_custom', [])
    narracao_custom = data.get('narracao_custom', '')

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

        if not modo_teste:
            yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': 'Gerando imagens...', 'progress': 18}) + '\n\n'
            erros = []
            for i, prompt in enumerate(prompts):
                num = str(i + 1).zfill(2)
                try:
                    img = leonardo_generate(prompt, formato, estilo)
                    sessions[session_id]['imagens'][i] = img
                    pct = 18 + int((i + 1) / max(len(prompts), 1) * 50)
                    yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': f'Imagem {num}/{len(prompts)} ok', 'progress': pct}) + '\n\n'
                except Exception as e:
                    erros.append(num)
                    yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': f'Imagem {num} falhou', 'progress': 18 + int((i + 1) / max(len(prompts), 1) * 50)}) + '\n\n'
            msg_imgs = f"{len(sessions[session_id]['imagens'])}/{len(prompts)} imagens geradas"
            if erros:
                msg_imgs += f" (falharam: {', '.join(erros)})"
            yield 'data:' + json.dumps({'step': 2, 'status': 'done', 'msg': msg_imgs, 'progress': 70}) + '\n\n'
            yield 'data:' + json.dumps({'imgs_total': len(prompts)}) + '\n\n'
        else:
            yield 'data:' + json.dumps({'step': 2, 'status': 'done', 'msg': 'Modo Teste - imagens nao geradas', 'progress': 70}) + '\n\n'

        yield 'data:' + json.dumps({'step': 3, 'status': 'active', 'msg': 'Gerando narracao...', 'progress': 72}) + '\n\n'
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
                if r.status_code == 200:
                    audio_data = r.content
                    audio_service = 'ElevenLabs'
        except:
            pass

        if not audio_data:
            try:
                from gtts import gTTS
                import io
                tts = gTTS(narracao_txt, lang='pt')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                audio_data = buf.getvalue()
                audio_service = 'gTTS'
            except:
                pass

        sessions[session_id]['audio'] = audio_data
        status_audio = 'done' if audio_data else 'error'
        msg_audio = f'Narracao gerada via {audio_service}' if audio_data else 'Erro na narracao'
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
                rot = f"TITULO: {data.get('titulo', '')}\n\nGANCHO: {data.get('gancho', '')}\n\n"
                for i, n in enumerate(narracao_txt.split('.')):
                    if n.strip():
                        rot += f"{str(i + 1).zfill(2)}. {n.strip()}.\n"
                zf.writestr('roteiro.txt', rot.encode('utf-8'))
                prompts_txt = '\n\n'.join([f"IMG {str(i + 1).zfill(2)}:\n{p}" for i, p in enumerate(prompts)])
                zf.writestr('prompts.txt', prompts_txt.encode('utf-8'))
            yield 'data:' + json.dumps({'step': 4, 'status': 'done', 'msg': 'Pronto! Clique para baixar', 'progress': 100, 'zip': zip_path}) + '\n\n'
        except Exception as e:
            yield 'data:' + json.dumps({'step': 4, 'status': 'error', 'msg': f'Erro ZIP: {str(e)}', 'erro': str(e)}) + '\n\n'

    return Response(stream(), mimetype='text/event-stream')

@app.route('/audio/<session_id>')
def audio(session_id):
    s = sessions.get(session_id)
    if not s or not s.get('audio'):
        return 'Nao encontrado', 404
    import io
    return send_file(io.BytesIO(s['audio']), mimetype='audio/mpeg')

@app.route('/imagem/<session_id>/<int:idx>')
def imagem(session_id, idx):
    s = sessions.get(session_id)
    if not s or idx not in s.get('imagens', {}):
        return 'Nao encontrado', 404
    import io
    return send_file(io.BytesIO(s['imagens'][idx]), mimetype='image/jpeg')

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
