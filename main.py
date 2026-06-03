import os, json, time, zipfile, requests, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template_string, Response

app = Flask(__name__)

# ---
CLAUDE_KEY     = os.environ.get("CLAUDE_API_KEY", "")
LEONARDO_KEY   = os.environ.get("LEONARDO_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# ---
sessions = {}

# ---
HISTORICO_FILE = "historico.json"

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r") as f:
            return json.load(f)
    return {"videos": []}

def salvar_historico(titulo, animais):
    h = carregar_historico()
    h["videos"].append({
        "titulo": titulo,
        "data": datetime.now().isoformat(),
        "animais": animais
    })
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

# ---
ESTILOS = {
    "stylized_game": "stylized game character art, non-realistic, vibrant colors, bold outlines, 9:16 vertical",
    "cinematic_doc": "cinematic wildlife documentary, hyper realistic, dramatic lighting, 9:16 vertical",
    "anime": "anime style illustration, vibrant colors, emotional scene, studio ghibli inspired, 9:16 vertical",
    "dark_fantasy": "dark fantasy illustration, epic composition, moody atmosphere, highly detailed, 9:16 vertical",
    "feature_film": "semi-realistic feature film illustration, cinematic color grading, volumetric lighting, highly detailed, 9:16 vertical",
    "macro_nature": "ultra macro nature photography, extreme detail, bokeh background, award winning wildlife photo, National Geographic style, 9:16 vertical",
    "anime_moderno": "modern anime illustration style, clean bold outlines, vibrant saturated colors, natural warm lighting, detailed background, expressive character, studio quality, 9:16 vertical",
    "cartoon_flat": "flat design cartoon illustration, clean vector art, bold outlines, solid vibrant colors, cute and expressive animal character, simple clean background, 2D animation style, no shadows, no gradients, 9:16 vertical"
}

# ---
FORMATOS = {
    "9:16": {"width": 768, "height": 1344},
    "16:9": {"width": 1344, "height": 768},
    "1:1":  {"width": 1024, "height": 1024}
}

# ---
DURACOES = {"30": 30, "50": 50, "60": 60, "90": 90, "90m": 90}
RITMOS   = {"lento": 3.0, "medio": 2.0, "rapido": 1.5}
PALAVRAS_POR_DURACAO = {"30": 65, "50": 108, "60": 130, "90": 195, "90m": 325}

def calc_imagens(duracao_str, ritmo_str, num_historias):
    dur = DURACOES.get(str(duracao_str), 60)
    rit = RITMOS.get(ritmo_str, 2.0)
    total = max(round(dur / rit), num_historias * 3 + 3)
    if num_historias == 1:
        return {"caso1": round(total*0.70), "caso2": 0, "caso3": 0, "final": round(total*0.30)}
    elif num_historias == 2:
        return {"caso1": round(total*0.40), "caso2": round(total*0.40), "caso3": 0, "final": round(total*0.20)}
    else:
        return {"caso1": round(total*0.25), "caso2": round(total*0.20), "caso3": round(total*0.25), "final": round(total*0.30)}

# ---
def build_system_roteiro(modelo, num_historias, dist, total_palavras):
    restricao = animais_recentes()
    restricao_txt = f"Animais usados nos últimos 7 dias — NÃO repita: {', '.join(restricao)}." if restricao else "Sem restrição de animais."

    filosofia_narracao = f"""
FILOSOFIA DE NARRAÇÃO — LEI ABSOLUTA:
A narração é um roteiro de filme. Uma história única que começa, respira, acelera, para, surpreende e termina.
O espectador não deve sentir que está sendo informado — deve sentir que está sendo puxado para dentro de algo que não consegue parar de ouvir.

REGRAS:
1. Cada frase flui naturalmente para a próxima. Use conectores: "Mas o que ninguém esperava era...", "E então algo impossível aconteceu.", "Isso sozinho já seria incrível. Mas espera."
2. Alterne frases curtas de impacto com frases médias descritivas.
3. Use detalhes específicos: nunca "muito tempo" — use "47 dias". Nunca "ficou triste" — use "parou de comer por 11 dias".
4. Cite o nome do animal explicitamente nas primeiras frases de cada história.
5. Transições naturais entre histórias: nunca "O próximo animal é..." — use "Mas não é o único." ou "Se isso já te surpreendeu, espera o que vem agora."
6. A narração inteira deve ter aproximadamente {total_palavras} palavras no total.
7. NUNCA use linguagem científica fria — use linguagem humana e envolvente.

ESTRUTURA EMOCIONAL:
- Gancho: impacto imediato, sem apresentação, vai direto
- História 1: sedução lenta, cria vínculo com o personagem
- Virada história 1: frases curtíssimas, sem fôlego
- Ponte: uma ou duas frases que prometem algo maior
- História 2: mais urgente, mais direto
- Micro-promessa: uma frase só, a mais poderosa até aqui
- História 3: choque, ritmo rápido, twist inevitável
- Revelação final: desacelera completamente, filosófico
- Pergunta divisora: direta, pessoal, divide opiniões

PROMPTS DE IMAGEM — REGRAS:
1. Cada prompt é a representação visual EXATA da frase de narração correspondente
2. Define características físicas únicas do animal no início de cada história e mantém em todos os prompts dessa história
3. Formato obrigatório: [descrição física do personagem] + [ação exata da cena] + [ângulo de câmera] + [iluminação] + [movimento]
4. Ângulos: close-up / wide shot / aerial / macro / over the shoulder
5. Iluminação: golden hour / single spotlight / soft natural light / blue hour / dramatic shadows
6. Movimento: mid-motion / frozen in the moment / slow motion
7. NUNCA use "cinematic", "realistic", "documentary" ou "photographic" — o estilo é adicionado pelo sistema
8. NUNCA use "an animal" — sempre o nome específico do animal
"""

    if modelo == "animais":
        especifico = f"""
Você cria roteiros virais sobre comportamento animal para YouTube.
{restricao_txt}

BANCO DE ANIMAIS:
- Caso 1 (familiar): Elefante africano, golfinho, cachorro, leão, gorila, urso polar, baleia jubarte, cavalo, lobo, orangotango, pinguim, tartaruga gigante, girafa, hipopótamo, tigre
- Caso 2 (médio): Corvo, orca, chimpanzé, lontra, hiena, falcão peregrino, polvo gigante, javali, texugo, capivara, morcego vampiro, canguru, alce, foca leopardo
- Caso 3 (inesperado): Abelha, formiga-cortadeira, borboleta Maculinea, peixe-zebra, polvo mimic, tarântula, vespa-esmeralda, louva-a-deus, lula colossal, medusa imortal Turritopsis
"""
    elif modelo == "psicologia":
        especifico = """
Você cria roteiros virais sobre psicologia humana para YouTube.
Os "casos" são comportamentos humanos em escalada: comum → surpreendente → perturbador.
A narração usa segunda pessoa: "Você faz isso", "Você já percebeu".
Os prompts mostram HUMANOS em situações cotidianas — não animais.
"""
    else:  # fatos
        especifico = """
Você cria roteiros virais sobre fatos científicos para YouTube.
Os "casos" são fatos que contradizem o senso comum: surpreendente → chocante → muda tudo.
A narração começa contradizendo uma crença: "Você acredita que X. A ciência prova que está errado."
Os prompts mostram: cérebros, experimentos, universo, natureza, descobertas científicas.
"""

    if num_historias == 1:
        estrutura = f"""
ESTRUTURA (1 história profunda):
- caso1: {dist['caso1']} prompts — história principal expandida com 6 sub-arcos: apresentacao, desenvolvimento, crise, escalada, twist, resolucao
- prompts_final: {dist['final']} prompts — revelação filosófica
- narracao_caso1: {dist['caso1']} frases
- narracao_final: {dist['final']} frases
"""
    elif num_historias == 2:
        estrutura = f"""
ESTRUTURA (2 histórias em contraste):
- caso1: {dist['caso1']} prompts — história familiar
- caso2: {dist['caso2']} prompts — história inesperada
- prompts_final: {dist['final']} prompts — revelação
- narracao_caso1: {dist['caso1']} frases, narracao_caso2: {dist['caso2']} frases, narracao_final: {dist['final']} frases
"""
    else:
        estrutura = f"""
ESTRUTURA (3 histórias em escalada):
- caso1: {dist['caso1']} prompts — familiar, interessante
- caso2: {dist['caso2']} prompts — médio, surpreendente
- caso3: {dist['caso3']} prompts — inesperado, chocante
- prompts_final: {dist['final']} prompts — revelação filosófica + espelho humano no último
- narracao_caso1: {dist['caso1']} frases, narracao_caso2: {dist['caso2']} frases, narracao_caso3: {dist['caso3']} frases, narracao_final: {dist['final']} frases
"""

    return f"""{especifico}
{filosofia_narracao}
{estrutura}

Responda SOMENTE em JSON válido sem markdown:
{{
  "pergunta_invisivel": "string",
  "emocao_ancora": "string",
  "tipo_gancho": "ESPELHO HUMANO | PROVOCAÇÃO | CONTRADIÇÃO | NÚMERO CURIOSO",
  "gancho_principal": "string",
  "gancho_opcoes": ["opcao2","opcao3","opcao4"],
  "caso1": {{
    "nome":"string","animal":"string","nivel":"string",
    "apresentacao":"string","tensao":"string","escalada":"string","twist":"string",
    "prompts":["array com {dist['caso1']} prompts em inglês"]
  }},
  "caso2": {{
    "nome":"string","animal":"string","nivel":"string",
    "apresentacao":"string","tensao":"string","escalada":"string","twist":"string",
    "prompts":["array com {dist['caso2']} prompts em inglês"]
  }},
  "caso3": {{
    "nome":"string","animal":"string","nivel":"string",
    "apresentacao":"string","tensao":"string","escalada":"string","twist":"string",
    "prompts":["array com {dist['caso3']} prompts em inglês"]
  }},
  "micro_promessa": "string",
  "prompts_final": ["array com {dist['final']} prompts em inglês"],
  "narracao_caso1": ["array com {dist['caso1']} frases em português"],
  "narracao_caso2": ["array com {dist['caso2']} frases em português"],
  "narracao_caso3": ["array com {dist['caso3']} frases em português"],
  "narracao_final": ["array com {dist['final']} frases em português"],
  "frase_final_principal": "string filosófica",
  "frase_final_opcoes": ["opcao2","opcao3","opcao4"],
  "pergunta_divisora_principal": "string",
  "pergunta_divisora_opcoes": ["opcao2","opcao3","opcao4"]
}}"""

# ---
def chamar_claude(system, user_msg, max_tokens=6000, modelo="claude-sonnet-4-5-20250929"):
    for tentativa in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": modelo,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user_msg}]
                },
                timeout=300
            )
            text = r.json()["content"][0]["text"]
            text = re.sub(r"```json|```", "", text).strip()
            return text
        except Exception as e:
            if tentativa == 2:
                raise Exception(f"Claude erro após 3 tentativas: {str(e)}")
            time.sleep(5)

# ---
def leonardo_generate(prompt, formato="9:16", estilo="stylized_game"):
    sufixo = ESTILOS.get(estilo, ESTILOS["stylized_game"])
    dims = FORMATOS.get(formato, FORMATOS["9:16"])
    prompt_full = prompt + ", " + sufixo

    for tentativa in range(3):
        try:
            r = requests.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                headers={"authorization": f"Bearer {LEONARDO_KEY}", "content-type": "application/json"},
                json={
                    "prompt": prompt_full,
                    "modelId": "aa77f04e-3eec-4034-9c07-d0f619684628",
                    "width": dims["width"],
                    "height": dims["height"],
                    "num_images": 1,
                    "guidance_scale": 10,
                    "negative_prompt": "blurry, low quality, distorted, ugly, bad anatomy, watermark, text, signature"
                },
                timeout=40
            )
            data = r.json()
            if "sdGenerationJob" not in data:
                raise Exception(f"Leonardo erro: {data}")
            gen_id = data["sdGenerationJob"]["generationId"]

            for _ in range(50):
                time.sleep(3)
                r2 = requests.get(
                    f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                    headers={"authorization": f"Bearer {LEONARDO_KEY}"},
                    timeout=15
                )
                imgs = r2.json().get("generations_by_pk", {}).get("generated_images", [])
                if imgs:
                    img_data = requests.get(imgs[0]["url"], timeout=20).content
                    return img_data

            raise Exception("Timeout aguardando imagem")
        except Exception as e:
            if tentativa == 2:
                raise
            time.sleep(5)

# ---
HTML = open("index.html", encoding="utf-8").read()


# ---
@app.route('/')
def index():
    return HTML

@app.route('/roteiro', methods=['POST'])
def roteiro():
    data = request.json
    titulo = data.get('titulo','').strip()
    contexto = data.get('contexto','').strip()
    modelo = data.get('modelo','animais')
    historias = int(data.get('historias', 3))
    duracao = str(data.get('duracao','50'))
    ritmo = data.get('ritmo','medio')

    dist = calc_imagens(duracao, ritmo, historias)
    total_palavras = PALAVRAS_POR_DURACAO.get(duracao, 130)
    system = build_system_roteiro(modelo, historias, dist, total_palavras)

    user_msg = f"Título: {titulo}"
    if contexto:
        user_msg += f"\nContexto: {contexto}"

    try:
        text = chamar_claude(system, user_msg)
        d = json.loads(text)
        # Salva animais no histórico
        animais = []
        for k in ['caso1','caso2','caso3']:
            if d.get(k,{}).get('animal'):
                animais.append(d[k]['animal'])
        if animais:
            salvar_historico(titulo, animais)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/gerar', methods=['POST'])
def gerar():
    data = request.json
    estilo = data.get('estilo','stylized_game')
    formato = data.get('formato','9:16')
    modo_teste = data.get('modo_teste', False)
    prompts_custom = data.get('prompts_custom', [])
    narracao_custom = data.get('narracao_custom','')

    # Monta narração
    if narracao_custom:
        narracao_txt = narracao_custom
    else:
        narracao_txt = ' '.join(filter(None, [
            data.get('gancho',''),
            *data.get('narracao_caso1',[]),
            *data.get('narracao_caso2',[]),
            data.get('micro_promessa',''),
            *data.get('narracao_caso3',[]),
            *data.get('narracao_final',[]),
            data.get('frase_final',''),
            data.get('pergunta_divisora','')
        ]))

    prompts = prompts_custom if prompts_custom else (
        data.get('caso1',{}).get('prompts',[]) +
        data.get('caso2',{}).get('prompts',[]) +
        data.get('caso3',{}).get('prompts',[]) +
        data.get('prompts_final',[])
    )

    session_id = str(int(time.time()))

    def stream():
        sessions[session_id] = {'imagens': {}, 'prompts': prompts, 'audio': None}

        yield 'data:' + json.dumps({'session_id': session_id}) + '\n\n'
        yield 'data:' + json.dumps({'step':1,'status':'done','msg':'Roteiro aprovado','progress':15}) + '\n\n'

        # Imagens
        if not modo_teste:
            yield 'data:' + json.dumps({'step':2,'status':'active','msg':'Gerando imagens...','progress':18}) + '\n\n'
            erros = []
            for i, prompt in enumerate(prompts):
                num = str(i+1).zfill(2)
                try:
                    img = leonardo_generate(prompt, formato, estilo)
                    sessions[session_id]['imagens'][i] = img
                    pct = 18 + int((i+1)/len(prompts)*50)
                    yield 'data:' + json.dumps({'step':2,'status':'active','msg':f'Imagem {num}/{len(prompts)} ✓','progress':pct}) + '\n\n'
                except Exception as e:
                    erros.append(num)
                    yield 'data:' + json.dumps({'step':2,'status':'active','msg':f'Imagem {num} ✗ — {str(e)[:50]}','progress':18+int((i+1)/len(prompts)*50)}) + '\n\n'

            msg_imgs = f"{len(sessions[session_id]['imagens'])}/{len(prompts)} imagens geradas"
            if erros: msg_imgs += f" · falharam: {', '.join(erros)}"
            yield 'data:' + json.dumps({'step':2,'status':'done','msg':msg_imgs,'progress':70}) + '\n\n'
            yield 'data:' + json.dumps({'imgs_total': len(prompts)}) + '\n\n'
        else:
            yield 'data:' + json.dumps({'step':2,'status':'done','msg':'Modo Teste — imagens não geradas','progress':70}) + '\n\n'

        # Áudio
        yield 'data:' + json.dumps({'step':3,'status':'active','msg':'Gerando narração...','progress':72}) + '\n\n'
        audio_data = None
        audio_service = ''
        try:
            if ELEVENLABS_KEY:
                r = requests.post(
                    f'https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}',
                    headers={'xi-api-key': ELEVENLABS_KEY, 'content-type': 'application/json'},
                    json={'text': narracao_txt, 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability':0.5,'similarity_boost':0.8}},
                    timeout=60
                )
                if r.status_code == 200:
                    audio_data = r.content
                    audio_service = 'ElevenLabs'
        except: pass

        if not audio_data:
            try:
                from gtts import gTTS
                import io
                tts = gTTS(narracao_txt, lang='pt')
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                audio_data = buf.getvalue()
                audio_service = 'gTTS'
            except: pass

        sessions[session_id]['audio'] = audio_data
        status_audio = 'done' if audio_data else 'error'
        msg_audio = f'Narração gerada via {audio_service}' if audio_data else 'Erro na narração'
        yield 'data:' + json.dumps({'step':3,'status':status_audio,'msg':msg_audio,'progress':88}) + '\n\n'

        if audio_data:
            yield 'data:' + json.dumps({'audio_url': f'/audio/{session_id}'}) + '\n\n'

        # ZIP
        yield 'data:' + json.dumps({'step':4,'status':'active','msg':'Criando ZIP...','progress':92}) + '\n\n'
        try:
            zip_path = f'/tmp/video_{session_id}.zip'
            with zipfile.ZipFile(zip_path,'w') as zf:
                for idx, img in sessions[session_id]['imagens'].items():
                    zf.writestr(f'IMG_{str(idx+1).zfill(2)}.jpg', img)
                if audio_data:
                    zf.writestr('narracao.mp3', audio_data)
                # Roteiro
                rot = f"TÍTULO: {data.get('titulo','')}\n\nGANCHO: {data.get('gancho','')}\n\n"
                for i, n in enumerate(narracao_txt.split('.')):
                    if n.strip(): rot += f"{str(i+1).zfill(2)}. {n.strip()}.\n"
                rot += f"\nFRASE FINAL: {data.get('frase_final','')}\nPERGUNTA DIVISORA: {data.get('pergunta_divisora','')}"
                zf.writestr('roteiro.txt', rot.encode('utf-8'))
                # Prompts
                prompts_txt = '\n\n'.join([f"IMG {str(i+1).zfill(2)}:\n{p}" for i,p in enumerate(prompts)])
                zf.writestr('prompts.txt', prompts_txt.encode('utf-8'))

            yield 'data:' + json.dumps({'step':4,'status':'done','msg':'Pronto! Clique para baixar','progress':100,'zip':zip_path}) + '\n\n'
        except Exception as e:
            yield 'data:' + json.dumps({'step':4,'status':'error','msg':f'Erro ZIP: {str(e)}','erro':str(e)}) + '\n\n'

    return Response(stream(), mimetype='text/event-stream')

@app.route('/audio/<session_id>')
def audio(session_id):
    s = sessions.get(session_id)
    if not s or not s.get('audio'):
        return 'Não encontrado', 404
    import io
    return send_file(io.BytesIO(s['audio']), mimetype='audio/mpeg')

@app.route('/imagem/<session_id>/<int:idx>')
def imagem(session_id, idx):
    s = sessions.get(session_id)
    if not s or idx not in s.get('imagens',{}):
        return 'Não encontrado', 404
    import io
    return send_file(io.BytesIO(s['imagens'][idx]), mimetype='image/jpeg')

@app.route('/download')
def download():
    f = request.args.get('file','')
    if not f or not f.startswith('/tmp/'):
        return 'Não encontrado', 404
    return send_file(f, as_attachment=True, download_name='video_youtube.zip')

@app.route('/traduzir', methods=['POST'])
def traduzir():
    prompt = request.json.get('prompt','')
    try:
        text = chamar_claude(
            "Traduza o prompt de imagem do inglês para o português de forma natural e clara. Retorne apenas a tradução, sem explicações.",
            prompt,
            max_tokens=500,
            modelo="claude-haiku-4-5-20251001"
        )
        return jsonify({'traducao': text})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/regenerar-imagem', methods=['POST'])
def regenerar_imagem():
    data = request.json
    session_id = data.get('session_id')
    idx = data.get('idx')
    prompt = data.get('prompt','')
    estilo = data.get('estilo','stylized_game')
    formato = data.get('formato','9:16')
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
    titulo = data.get('titulo','')
    tipo = data.get('tipo','gancho')
    modelo = data.get('modelo','animais')
    tipos_map = {
        'gancho': 'Gere 4 opções de gancho para o título fornecido. Retorne JSON: {"opcoes":["op1","op2","op3","op4"]}',
        'frase': 'Gere 4 opções de frase final filosófica para o título fornecido. Retorne JSON: {"opcoes":["op1","op2","op3","op4"]}',
        'pergunta': 'Gere 4 opções de pergunta divisora que divide opiniões para o título fornecido. Retorne JSON: {"opcoes":["op1","op2","op3","op4"]}'
    }
    try:
        text = chamar_claude(tipos_map.get(tipo,''), f"Título: {titulo}", max_tokens=500, modelo="claude-haiku-4-5-20251001")
        d = json.loads(text)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/clonar', methods=['POST'])
def clonar():
    data = request.json
    transcricao = data.get('transcricao','')
    titulo = data.get('titulo','')
    obs = data.get('obs','')
    duracao = str(data.get('duracao','50'))
    estilo = data.get('estilo','stylized_game')

    system = """Você é especialista em análise e clonagem de estrutura narrativa de vídeos virais do YouTube.

PASSO 1 — Analise a transcrição e identifique:
- modelo_identificado: "animais", "psicologia" ou "fatos"
- Estrutura do gancho, ritmo, gatilhos emocionais, transições

PASSO 2 — Clone a estrutura com o novo tema fornecido.
Mantém ritmo, tom, proporção de frases. Conteúdo 100% original.

Responda em JSON no mesmo formato padrão do sistema com campo adicional modelo_identificado."""

    user_msg = f"Transcrição:\n{transcricao}\n\nNovo título: {titulo}\nObservações: {obs}"
    try:
        text = chamar_claude(system, user_msg)
        d = json.loads(text)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)


    user_msg = f"Transcrição:\n{transcricao}\n\nNovo título: {titulo}\nObservações: {obs}"
    try:
        text = chamar_claude(system, user_msg)
        d = json.loads(text)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
