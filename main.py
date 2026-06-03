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
    restr = "Animais usados nos ultimos 7 dias - NAO repita: " + ", ".join(restricao) + "." if restricao else "Sem restricao de animais."

    if modelo == "psicologia":
        ctx = "Voce e especialista em roteiros virais de psicologia humana. Os casos sao comportamentos humanos: comum, surpreendente, perturbador. Narracao em segunda pessoa. Prompts mostram HUMANOS."
    elif modelo == "fatos":
        ctx = "Voce e especialista em roteiros virais de ciencia. Os casos contradizem crencas populares. Prompts mostram ciencia e descobertas."
    else:
        ctx = ("Voce e especialista em roteiros virais de comportamento animal. " + restr + "\n"
               "ANIMAIS: Caso 1 = FAMILIAR (elefante, golfinho, cachorro, leao, gorila, urso, baleia, lobo). "
               "Caso 2 = MEDIO (corvo, orca, chimpanze, lontra, hiena, falcao, polvo, texugo). "
               "Caso 3 = INESPERADO nunca obvio (vespa-esmeralda, medusa imortal, tardigrado, polvo mimic, louva-a-deus). "
               "NUNCA repita animais entre as 3 historias.")

    if nh == 1:
        struct = ("ESTRUTURA 1 historia: caso1=" + str(dist['caso1']) + " prompts+" + str(dist['caso1']) + " frases. "
                  "prompts_final=" + str(dist['final']) + " prompts. narracao_final=" + str(dist['final']) + " frases.")
    elif nh == 2:
        struct = ("ESTRUTURA 2 historias: caso1=" + str(dist['caso1']) + " prompts+" + str(dist['caso1']) + " frases. "
                  "caso2=" + str(dist['caso2']) + " prompts+" + str(dist['caso2']) + " frases. "
                  "prompts_final=" + str(dist['final']) + ". narracao_final=" + str(dist['final']) + " frases.")
    else:
        struct = ("ESTRUTURA 3 historias em escalada: "
                  "caso1=" + str(dist['caso1']) + " prompts+" + str(dist['caso1']) + " frases (Interessante). "
                  "caso2=" + str(dist['caso2']) + " prompts+" + str(dist['caso2']) + " frases (Surpreendente). "
                  "caso3=" + str(dist['caso3']) + " prompts+" + str(dist['caso3']) + " frases (Chocante). "
                  "prompts_final=" + str(dist['final']) + " prompts (ULTIMO = espelho humano). "
                  "narracao_final=" + str(dist['final']) + " frases.")

    system = (ctx + "\n\n"
        "PSICOLOGIA DO ROTEIRO:\n"
        "1. EMOCAO-ANCORA: defina uma emocao central que conecta tudo ao espectador. Exemplos: reconhecimento culpado, admiracao perturbadora, identificacao involuntaria.\n"
        "2. PERGUNTA INVISIVEL: uma pergunta que o video responde sem nunca dizer em voz alta. Ela vive na cabeca do espectador.\n"
        "3. GANCHO — escolha o tipo mais poderoso: PROVOCACAO (afirmacao que desafia), CONTRADICAO (quebra crenca), ESPELHO HUMANO (animal faz algo humano demais), NUMERO CURIOSO (dado especifico que para o scroll). O gancho vai DIRETO — sem apresentacao do video.\n\n"
        "SUB-ARCOS DE CADA HISTORIA (OBRIGATORIOS):\n"
        "- Apresentacao 2s: UM detalhe unico e humanizante do personagem\n"
        "- Tensao 3-4s: algo esta errado, o espectador pressente\n"
        "- Escalada 4-5s: situacao piora, detalhes ficam mais especificos\n"
        "- Twist 2-3s: revelacao que muda tudo — o espectador NAO esperava\n\n"
        "MICRO-PROMESSA entre caso 2 e 3: frase que promete algo maior. NUNCA use transicao mecanica como O proximo animal e.\n\n"
        "NARRACAO — REGRAS ABSOLUTAS:\n"
        "1. Frases COMPLETAS com sujeito, verbo e sentido — nunca frase cortada no meio\n"
        "2. Nome do animal explicitamente nas primeiras frases — nunca so ele ou ela sem apresentar\n"
        "3. Detalhes especificos: nunca muito tempo, use 47 dias. Nunca ficou triste, use parou de comer 11 dias\n"
        "4. Ritmo variado: alterne frases curtas de impacto (3-5 palavras) com frases medias (10-15 palavras)\n"
        "5. Conectores naturais: Mas o que ninguem esperava era... E entao algo impossivel aconteceu.\n"
        "6. Transicoes organicas: nunca O proximo animal e. Use Mas nao e o unico. ou Se isso ja te surpreendeu...\n"
        "7. Viradas em rafagas: Ele nao foi embora. Ficou. Por tres dias. Olhando.\n"
        "8. SEM REPETICAO: cada frase avanca a historia — nunca repita a mesma ideia\n"
        "9. Pontuacao correta: ponto final, exclamacao ou interrogacao. Nunca termine com virgula\n"
        "10. Total aproximado: " + str(total_palavras) + " palavras para TODA a narracao\n\n"
        "PROMPTS DE IMAGEM:\n"
        "1. Cada prompt e par EXATO da frase de narracao correspondente\n"
        "2. Define fisico unico do animal no inicio de cada historia e repete em todos os prompts dessa historia\n"
        "3. Formato: [fisico especifico] + [acao exata] + [angulo camera] + [iluminacao] + [movimento]\n"
        "4. NUNCA use cinematic, realistic, documentary — o estilo e adicionado pelo sistema\n"
        "5. NUNCA use an animal — sempre o nome especifico\n\n"
        + struct + "\n\n"
        "Responda SOMENTE em JSON valido sem markdown:\n"
        "{\n"
        '  "pergunta_invisivel": "string",\n'
        '  "emocao_ancora": "string",\n'
        '  "tipo_gancho": "PROVOCACAO | CONTRADICAO | ESPELHO HUMANO | NUMERO CURIOSO",\n'
        '  "gancho_principal": "string — primeira frase, vai direto sem apresentacao",\n'
        '  "gancho_opcoes": ["variacao2","variacao3","variacao4"],\n'
        '  "caso1": {"nome":"string","animal":"string","nivel":"Interessante","apresentacao":"string","tensao":"string","escalada":"string","twist":"string","prompts":["' + str(dist['caso1']) + ' prompts ingles"]},\n'
        '  "caso2": {"nome":"string","animal":"string","nivel":"Surpreendente","apresentacao":"string","tensao":"string","escalada":"string","twist":"string","prompts":["' + str(dist['caso2']) + ' prompts ingles"]},\n'
        '  "caso3": {"nome":"string","animal":"string","nivel":"Chocante","apresentacao":"string","tensao":"string","escalada":"string","twist":"string","prompts":["' + str(dist['caso3']) + ' prompts ingles"]},\n'
        '  "micro_promessa": "string — sem transicao mecanica",\n'
        '  "prompts_final": ["' + str(dist['final']) + ' prompts ingles — ultimo e espelho humano"],\n'
        '  "narracao_caso1": ["' + str(dist['caso1']) + ' frases portugues — fluidas completas"],\n'
        '  "narracao_caso2": ["' + str(dist['caso2']) + ' frases portugues"],\n'
        '  "narracao_caso3": ["' + str(dist['caso3']) + ' frases portugues"],\n'
        '  "narracao_final": ["' + str(dist['final']) + ' frases portugues — ultima e filosofica"],\n'
        '  "frase_final_principal": "string filosofica lenta e profunda",\n'
        '  "frase_final_opcoes": ["variacao2","variacao3","variacao4"],\n'
        '  "pergunta_divisora_principal": "string — divide opinioes sem resposta obvia",\n'
        '  "pergunta_divisora_opcoes": ["variacao2","variacao3","variacao4"]\n'
        "}")
    return system

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
                    # Salva também em disco como backup
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


@app.route('/narracao', methods=['POST'])
def gerar_narracao():
    data = request.json
    narracao_custom = data.get('narracao_custom', '')
    gancho = data.get('gancho', '')
    frase_final = data.get('frase_final', '')
    pergunta_divisora = data.get('pergunta_divisora', '')

    partes = [p for p in [gancho, narracao_custom, frase_final, pergunta_divisora] if p]
    narracao_txt = ' '.join(partes) if partes else narracao_custom

    session_id = str(int(time.time()))
    sessions[session_id] = {'imagens': {}, 'prompts': [], 'audio': None}

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

    if audio_data:
        return jsonify({'ok': True, 'session_id': session_id, 'audio_url': f'/audio/{session_id}', 'servico': audio_service})
    else:
        return jsonify({'erro': 'Erro ao gerar narracao'}), 500

@app.route('/audio/<session_id>')
def audio(session_id):
    s = sessions.get(session_id)
    if not s or not s.get('audio'):
        return 'Nao encontrado', 404
    import io
    return send_file(io.BytesIO(s['audio']), mimetype='audio/mpeg')

@app.route('/imagem/<session_id>/<int:idx>')
def imagem(session_id, idx):
    import io
    # Tenta primeiro na RAM
    s = sessions.get(session_id)
    if s and idx in s.get('imagens', {}):
        return send_file(io.BytesIO(s['imagens'][idx]), mimetype='image/jpeg')
    # Tenta no disco
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
