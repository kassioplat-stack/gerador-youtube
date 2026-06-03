import os, json, time, zipfile, requests, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template_string, Response

app = Flask(__name__)

# ── API Keys ──────────────────────────────────────────────────────────────────
CLAUDE_KEY     = os.environ.get("CLAUDE_API_KEY", "")
LEONARDO_KEY   = os.environ.get("LEONARDO_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# ── Sessões em memória ────────────────────────────────────────────────────────
sessions = {}

# ── Histórico de animais ──────────────────────────────────────────────────────
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

# ── Estilos visuais ───────────────────────────────────────────────────────────
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

# ── Formatos ──────────────────────────────────────────────────────────────────
FORMATOS = {
    "9:16": {"width": 768, "height": 1344},
    "16:9": {"width": 1344, "height": 768},
    "1:1":  {"width": 1024, "height": 1024}
}

# ── Cálculo de imagens por ritmo ──────────────────────────────────────────────
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

# ── SYSTEM PROMPTs ────────────────────────────────────────────────────────────
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

# ── Chamar Claude ─────────────────────────────────────────────────────────────
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

# ── Gerar imagem no Leonardo ──────────────────────────────────────────────────
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

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = open("index.html").read() if os.path.exists("index.html") else """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gerador YouTube</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f0f0f;color:#fff;min-height:100vh;padding:2rem}
.container{max-width:700px;margin:0 auto}
.logo{font-size:11px;font-weight:600;color:#E8593C;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}
h1{font-size:26px;font-weight:700;margin-bottom:4px}
.sub{font-size:14px;color:#555;margin-bottom:2rem}
.tabs{display:flex;gap:0;margin-bottom:1.5rem;border-bottom:1px solid #222}
.tab{padding:10px 20px;font-size:13px;font-weight:500;color:#555;cursor:pointer;border-bottom:2px solid transparent;transition:all .15s;background:none;border-top:none;border-left:none;border-right:none;font-family:inherit}
.tab.active{color:#E8593C;border-bottom-color:#E8593C}
.tab-content{display:none}.tab-content.active{display:block}
.card{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:1.25rem;margin-bottom:1rem}
.slbl{font-size:11px;font-weight:600;color:#444;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:8px}
input[type=text],textarea{width:100%;background:#111;border:1px solid #333;border-radius:8px;padding:10px 12px;font-size:14px;color:#fff;font-family:inherit;outline:none;transition:border-color .2s;margin-bottom:8px}
input[type=text]:focus,textarea:focus{border-color:#E8593C}
textarea{height:60px;resize:none}
.model-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:1rem}
.model-card,.style-card,.config-card{background:#111;border:1px solid #2a2a2a;border-radius:10px;padding:10px;cursor:pointer;transition:all .15s;text-align:left}
.model-card.sel,.style-card.sel,.config-card.sel{border-color:#E8593C;background:#1f1510}
.mc-icon{font-size:18px;margin-bottom:4px}
.mc-name{font-size:12px;font-weight:500;color:#ccc}
.mc-desc{font-size:11px;color:#444;margin-top:2px}
.model-card.sel .mc-name,.style-card.sel .mc-name,.config-card.sel .mc-name{color:#E8593C}
.style-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:1rem}
.config-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:1rem}
.config-block{background:#111;border:1px solid #2a2a2a;border-radius:10px;padding:10px}
.chips-row{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.chip{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:20px;padding:4px 10px;font-size:11px;color:#555;cursor:pointer;transition:all .15s;font-family:inherit}
.chip.sel{background:#1f1510;border-color:#E8593C;color:#E8593C}
.toggle-row{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.toggle{position:relative;width:40px;height:22px;background:#333;border-radius:11px;cursor:pointer;transition:background .2s}
.toggle.on{background:#E8593C}
.toggle-knob{position:absolute;top:3px;left:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:left .2s}
.toggle.on .toggle-knob{left:21px}
.toggle-label{font-size:13px;color:#777}
.preview-info{font-size:12px;color:#333;margin-top:8px;text-align:center}
.btn{width:100%;border:none;border-radius:8px;padding:12px;font-size:15px;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity .2s;margin-top:4px}
.btn-primary{background:#E8593C;color:#fff}
.btn-secondary{background:#1a3a5c;color:#fff}
.btn:hover{opacity:.85}
.btn:disabled{opacity:.4;cursor:not-allowed}
.steps-card{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:1.25rem;margin-bottom:1rem;display:none}
.step{display:flex;gap:12px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #222}
.step:last-child{border:none}
.dot{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;background:#222;color:#444;transition:all .3s}
.dot.active{background:#E8593C;color:#fff}
.dot.done{background:#1a6b3c;color:#fff}
.dot.error{background:#6b1a1a;color:#fff}
.step-title{font-size:13px;font-weight:500;color:#bbb;margin-bottom:2px}
.step-desc{font-size:12px;color:#444;transition:color .3s}
.step-desc.active{color:#E8593C}
.step-desc.done{color:#27a05a}
.step-desc.error{color:#e85c5c}
.progress-bar{height:3px;background:#222;border-radius:3px;margin-top:12px;overflow:hidden}
.progress-fill{height:100%;background:#E8593C;width:0%;transition:width .4s;border-radius:3px}
.result-card{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:1.25rem;margin-bottom:1rem;display:none}
.download-btn{display:block;width:100%;background:#1a6b3c;color:#fff;border:none;border-radius:8px;padding:14px;font-size:15px;font-weight:700;cursor:pointer;text-align:center;text-decoration:none;transition:opacity .2s;font-family:inherit}
.download-btn:hover{opacity:.85}
.info-box{background:#111;border:1px solid #222;border-radius:8px;padding:12px;margin-top:10px;font-size:12px;color:#444;line-height:1.7}
.audio-player{width:100%;margin-top:10px;filter:invert(1) hue-rotate(180deg)}
.img-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:12px}
.img-cell{position:relative;aspect-ratio:9/16;background:#111;border-radius:6px;overflow:hidden;border:2px solid transparent;cursor:pointer;transition:border-color .2s}
.img-cell:hover{border-color:#555}
.img-cell.sel{border-color:#E8593C}
.img-cell img{width:100%;height:100%;object-fit:cover}
.img-num{position:absolute;top:4px;left:4px;background:rgba(0,0,0,.7);color:#fff;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px}
.img-regen{position:absolute;top:4px;right:4px;background:rgba(232,89,60,.9);color:#fff;border:none;border-radius:4px;padding:2px 6px;font-size:10px;cursor:pointer;font-family:inherit;display:none}
.img-cell:hover .img-regen{display:block}
.lightbox{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.9);z-index:1000;align-items:center;justify-content:center;flex-direction:column;gap:12px}
.lightbox.open{display:flex}
.lightbox img{max-height:80vh;max-width:90vw;border-radius:8px;object-fit:contain}
.lightbox-close{position:absolute;top:20px;right:20px;background:none;border:none;color:#fff;font-size:24px;cursor:pointer}
.lightbox-prompt{max-width:600px;text-align:center;font-size:13px;color:#aaa;padding:0 1rem}
.prompt-edit{width:100%;background:#111;border:1px solid #333;border-radius:6px;padding:8px;font-size:12px;color:#fff;font-family:inherit;margin-top:8px;resize:none;height:60px}
.regen-single{background:#E8593C;color:#fff;border:none;border-radius:6px;padding:6px 14px;font-size:12px;cursor:pointer;font-family:inherit;margin-top:6px}
.calendar-list{display:flex;flex-direction:column;gap:8px}
.cal-item{background:#111;border:1px solid #2a2a2a;border-radius:8px;padding:10px 14px;display:flex;align-items:center;gap:12px}
.cal-status{font-size:10px;font-weight:600;border-radius:4px;padding:2px 8px}
.cs-plan{background:#1a3a5c;color:#5b9bd5}
.cs-ready{background:#1a6b3c;color:#27a05a}
.cal-title{font-size:13px;color:#ccc;flex:1}
.cal-date{font-size:11px;color:#444}
.cal-btn{background:#E8593C;color:#fff;border:none;border-radius:6px;padding:4px 12px;font-size:11px;cursor:pointer;font-family:inherit}
.add-row{display:flex;gap:8px;margin-bottom:1rem}
.add-row input{flex:1;margin:0}
.gancho-opts{display:flex;flex-direction:column;gap:6px;margin-top:8px}
.gancho-opt{background:#111;border:1px solid #2a2a2a;border-radius:8px;padding:10px 12px;cursor:pointer;font-size:13px;color:#ccc;transition:all .15s}
.gancho-opt.sel{border-color:#E8593C;color:#fff}
.gancho-opt:hover{border-color:#555}
.regen-opts-btn{background:transparent;border:1px solid #333;border-radius:6px;padding:4px 10px;font-size:11px;color:#555;cursor:pointer;font-family:inherit;margin-top:6px}
.regen-opts-btn:hover{border-color:#E8593C;color:#E8593C}
@media(max-width:500px){.model-grid{grid-template-columns:1fr 1fr}.style-grid{grid-template-columns:repeat(2,1fr)}.config-row{grid-template-columns:1fr}.img-grid{grid-template-columns:repeat(3,1fr)}}
</style>
</head>
<body>
<div class="container">
  <div class="logo">▶ Pipeline YouTube</div>
  <h1>Gerador de Vídeos</h1>
  <p class="sub">Escolha o modelo → configure → 1 clique</p>

  <div class="tabs">
    <button class="tab active" onclick="showTab('gerar',this)">Gerar</button>
    <button class="tab" onclick="showTab('clonar',this)">Clonar Roteiro</button>
    <button class="tab" onclick="showTab('calendario',this)">Calendário</button>
  </div>

  <!-- ABA GERAR -->
  <div class="tab-content active" id="tab-gerar">

    <div class="card">
      <span class="slbl">Modelo de conteúdo</span>
      <div class="model-grid">
        <button class="model-card sel" onclick="selModel('animais',this)">
          <div class="mc-icon">🐾</div>
          <div class="mc-name">Comportamento Animal</div>
          <div class="mc-desc">3 animais em escalada</div>
        </button>
        <button class="model-card" onclick="selModel('psicologia',this)">
          <div class="mc-icon">🧠</div>
          <div class="mc-name">Psicologia Humana</div>
          <div class="mc-desc">3 comportamentos humanos</div>
        </button>
        <button class="model-card" onclick="selModel('fatos',this)">
          <div class="mc-icon">💡</div>
          <div class="mc-name">Fatos & Percepção</div>
          <div class="mc-desc">3 fatos científicos</div>
        </button>
      </div>
    </div>

    <div class="card">
      <span class="slbl">Título do vídeo</span>
      <input type="text" id="titulo" placeholder="Ex: Narcisistas da Floresta" />
      <span class="slbl">Contexto do título (opcional)</span>
      <textarea id="contexto" placeholder="Descreva o ângulo, animais específicos, tom da história..."></textarea>
    </div>

    <div class="card">
      <span class="slbl">Estilo visual</span>
      <div class="style-grid">
        <button class="style-card sel" onclick="selStyle('stylized_game',this)"><div class="mc-icon">🎮</div><div class="mc-name">Stylized Game</div></button>
        <button class="style-card" onclick="selStyle('cinematic_doc',this)"><div class="mc-icon">🎬</div><div class="mc-name">Cinematic Doc</div></button>
        <button class="style-card" onclick="selStyle('anime',this)"><div class="mc-icon">🌸</div><div class="mc-name">Anime</div></button>
        <button class="style-card" onclick="selStyle('dark_fantasy',this)"><div class="mc-icon">⚔️</div><div class="mc-name">Dark Fantasy</div></button>
        <button class="style-card" onclick="selStyle('feature_film',this)"><div class="mc-icon">🎥</div><div class="mc-name">Feature Film</div></button>
        <button class="style-card" onclick="selStyle('macro_nature',this)"><div class="mc-icon">🔬</div><div class="mc-name">Macro Nature</div></button>
        <button class="style-card" onclick="selStyle('anime_moderno',this)"><div class="mc-icon">🎌</div><div class="mc-name">Anime Moderno</div></button>
        <button class="style-card" onclick="selStyle('cartoon_flat',this)"><div class="mc-icon">🎨</div><div class="mc-name">Cartoon Flat</div></button>
      </div>
    </div>

    <div class="config-row">
      <div class="config-block">
        <span class="slbl">Nº de histórias</span>
        <div class="chips-row">
          <button class="chip" onclick="selChip(this,'historias','1')">1 história</button>
          <button class="chip" onclick="selChip(this,'historias','2')">2 histórias</button>
          <button class="chip sel" onclick="selChip(this,'historias','3')">3 histórias</button>
        </div>
      </div>
      <div class="config-block">
        <span class="slbl">Formato</span>
        <div class="chips-row">
          <button class="chip sel" onclick="selChip(this,'formato','9:16')">9:16</button>
          <button class="chip" onclick="selChip(this,'formato','16:9')">16:9</button>
          <button class="chip" onclick="selChip(this,'formato','1:1')">1:1</button>
        </div>
      </div>
    </div>

    <div class="config-row">
      <div class="config-block">
        <span class="slbl">Duração do vídeo</span>
        <div class="chips-row">
          <button class="chip" onclick="selChip(this,'duracao','30')">30s</button>
          <button class="chip sel" onclick="selChip(this,'duracao','50')">50s</button>
          <button class="chip" onclick="selChip(this,'duracao','60')">60s</button>
          <button class="chip" onclick="selChip(this,'duracao','90')">90s</button>
          <button class="chip" onclick="selChip(this,'duracao','90m')">1:30</button>
        </div>
      </div>
      <div class="config-block">
        <span class="slbl">Ritmo de corte</span>
        <div class="chips-row">
          <button class="chip" onclick="selChip(this,'ritmo','lento')">Lento 3s/img</button>
          <button class="chip sel" onclick="selChip(this,'ritmo','medio')">Médio 2s/img</button>
          <button class="chip" onclick="selChip(this,'ritmo','rapido')">Rápido 1.5s/img</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="toggle-row">
        <div class="toggle" id="toggle-teste" onclick="toggleTeste()"><div class="toggle-knob"></div></div>
        <span class="toggle-label">Modo Teste — só roteiro e narração, sem gerar imagens</span>
      </div>
      <div id="preview-info" class="preview-info"></div>
      <button class="btn btn-secondary" id="btn-roteiro" onclick="gerarRoteiro()">📝 Gerar Roteiro</button>
      <button class="btn btn-primary" id="btn-imagens" onclick="gerarImagens()" disabled style="margin-top:8px;opacity:.4">▶ Gerar Imagens e Áudio</button>
      <div class="progress-bar"><div class="progress-fill" id="progress"></div></div>
    </div>

    <div class="steps-card" id="steps-card">
      <div class="step"><div class="dot" id="d1">1</div><div><div class="step-title">Roteiro — Claude</div><div class="step-desc" id="s1">Aguardando...</div></div></div>
      <div class="step"><div class="dot" id="d2">2</div><div><div class="step-title">Imagens — Leonardo.ai</div><div class="step-desc" id="s2">Aguardando...</div></div></div>
      <div class="step"><div class="dot" id="d3">3</div><div><div class="step-title">Narração — ElevenLabs/gTTS</div><div class="step-desc" id="s3">Aguardando...</div></div></div>
      <div class="step"><div class="dot" id="d4">4</div><div><div class="step-title">Empacotando ZIP</div><div class="step-desc" id="s4">Aguardando...</div></div></div>
    </div>

    <!-- Preview do roteiro -->
    <div id="roteiro-preview" style="display:none">
      <div class="card">
        <span class="slbl">Gancho — escolha uma opção</span>
        <div class="gancho-opts" id="gancho-opts"></div>
        <button class="regen-opts-btn" onclick="regenerarOpcoes('gancho')">↺ Regenerar ganchos</button>
      </div>
      <div class="card">
        <span class="slbl">Narração completa</span>
        <textarea id="narracao-edit" style="height:200px"></textarea>
      </div>
      <div class="card">
        <span class="slbl">Prompts de imagem</span>
        <div id="prompts-list"></div>
      </div>
      <div class="card">
        <span class="slbl">Frase final — escolha uma opção</span>
        <div class="gancho-opts" id="frase-opts"></div>
        <button class="regen-opts-btn" onclick="regenerarOpcoes('frase')">↺ Regenerar frases finais</button>
      </div>
      <div class="card">
        <span class="slbl">Pergunta divisora — escolha uma opção</span>
        <div class="gancho-opts" id="pergunta-opts"></div>
        <button class="regen-opts-btn" onclick="regenerarOpcoes('pergunta')">↺ Regenerar perguntas</button>
      </div>
    </div>

    <div class="result-card" id="result-card">
      <audio id="audio-player" class="audio-player" controls style="display:none"></audio>
      <button class="download-btn" id="dl-btn">⬇ Baixar ZIP — imagens + áudio</button>
      <div class="info-box">
        <strong>ZIP contém:</strong> imagens numeradas + narracao.mp3 + roteiro.txt + timing.txt<br>
        <strong>CapCut:</strong> importe o áudio → encaixe as imagens na forma de onda → exporte 9:16
      </div>
      <div id="img-grid" class="img-grid"></div>
    </div>

    <!-- Lightbox -->
    <div class="lightbox" id="lightbox">
      <button class="lightbox-close" onclick="closeLightbox()">✕</button>
      <img id="lb-img" src="" alt=""/>
      <div class="lightbox-prompt">
        <div id="lb-num" style="font-size:11px;color:#555;margin-bottom:4px"></div>
        <div id="lb-prompt-text" style="font-size:12px;color:#888"></div>
        <textarea class="prompt-edit" id="lb-prompt-edit"></textarea>
        <button class="regen-single" onclick="regenSingle()">↺ Regenerar esta imagem</button>
      </div>
    </div>

  </div><!-- /tab-gerar -->

  <!-- ABA CLONAR -->
  <div class="tab-content" id="tab-clonar">
    <div class="card">
      <span class="slbl">Transcrição do vídeo original</span>
      <textarea id="transcricao" style="height:150px" placeholder="Cole aqui o texto completo da narração do vídeo que quer clonar..."></textarea>
      <span class="slbl">Seu título</span>
      <input type="text" id="titulo-clone" placeholder="Qual tema você quer usar com essa estrutura?"/>
      <span class="slbl">Observações (opcional)</span>
      <textarea id="obs-clone" style="height:50px" placeholder="Ex: ritmo muito rápido, histórias curtas e diretas..."></textarea>
    </div>
    <div class="config-row">
      <div class="config-block">
        <span class="slbl">Duração</span>
        <div class="chips-row">
          <button class="chip" onclick="selChip(this,'duracao-clone','30')">30s</button>
          <button class="chip sel" onclick="selChip(this,'duracao-clone','50')">50s</button>
          <button class="chip" onclick="selChip(this,'duracao-clone','60')">60s</button>
          <button class="chip" onclick="selChip(this,'duracao-clone','90')">90s</button>
        </div>
      </div>
      <div class="config-block">
        <span class="slbl">Estilo visual</span>
        <div class="chips-row">
          <button class="chip sel" onclick="selChip(this,'estilo-clone','stylized_game')">Stylized Game</button>
          <button class="chip" onclick="selChip(this,'estilo-clone','anime')">Anime</button>
          <button class="chip" onclick="selChip(this,'estilo-clone','cartoon_flat')">Cartoon</button>
        </div>
      </div>
    </div>
    <button class="btn btn-secondary" onclick="clonarRoteiro()">🔍 Analisar e Clonar</button>
    <div id="clone-result" style="margin-top:1rem;font-size:13px;color:#777"></div>
  </div>

  <!-- ABA CALENDÁRIO -->
  <div class="tab-content" id="tab-calendario">
    <div class="card">
      <span class="slbl">Adicionar título à fila</span>
      <div class="add-row">
        <input type="text" id="cal-titulo" placeholder="Título do vídeo..."/>
        <input type="date" id="cal-data" style="width:150px;margin:0"/>
        <button class="btn btn-primary" style="width:auto;padding:8px 16px;margin:0" onclick="addCalendario()">+</button>
      </div>
      <div class="calendar-list" id="cal-list"></div>
    </div>
  </div>

</div><!-- /container -->

<script>
// ── Estado ─────────────────────────────────────────────────────────────────
var state = {
  modelo: 'animais',
  estilo: 'stylized_game',
  historias: '3',
  formato: '9:16',
  duracao: '50',
  ritmo: 'medio',
  modoTeste: false,
  roteiro: null,
  prompts: [],
  sessionId: null,
  imgData: [],
  lbIdx: -1,
  calendarioItems: JSON.parse(localStorage.getItem('calendario') || '[]')
};

// ── Tabs ───────────────────────────────────────────────────────────────────
function showTab(id, btn) {
  document.querySelectorAll('.tab-content').forEach(function(t){ t.classList.remove('active'); });
  document.querySelectorAll('.tab').forEach(function(t){ t.classList.remove('active'); });
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
  if(id === 'calendario') renderCalendario();
}

// ── Seletores ─────────────────────────────────────────────────────────────
function selModel(val, btn) {
  state.modelo = val;
  btn.closest('.model-grid').querySelectorAll('.model-card').forEach(function(b){ b.classList.remove('sel'); });
  btn.classList.add('sel');
  var placeholders = {animais:'Ex: Narcisistas da Floresta', psicologia:'Ex: Por que você procrastina mesmo sabendo que é errado', fatos:'Ex: 3 coisas que você acredita sobre o cérebro que são falsas'};
  document.getElementById('titulo').placeholder = placeholders[val];
  updatePreviewInfo();
}

function selStyle(val, btn) {
  state.estilo = val;
  btn.closest('.style-grid').querySelectorAll('.style-card').forEach(function(b){ b.classList.remove('sel'); });
  btn.classList.add('sel');
}

function selChip(btn, group, val) {
  var key = group.replace(/-/g,'_');
  state[key] = val;
  var row = btn.closest('.chips-row');
  if(row) {
    row.querySelectorAll('.chip').forEach(function(b){ b.classList.remove('sel'); });
  }
  btn.classList.add('sel');
  updatePreviewInfo();
}

function updatePreviewInfo() {
  var dur = {30:30,50:50,60:60,90:90,'90m':90}[state.duracao] || 60;
  var rit = {lento:3.0,medio:2.0,rapido:1.5}[state.ritmo] || 2.0;
  var imgs = Math.round(dur / rit);
  document.getElementById('preview-info').textContent = 'Serão geradas ~' + imgs + ' imagens em ' + state.duracao + 's · ritmo de ' + rit + 's/imagem';
}

function toggleTeste() {
  state.modoTeste = !state.modoTeste;
  var t = document.getElementById('toggle-teste');
  t.classList.toggle('on', state.modoTeste);
}

updatePreviewInfo();

// ── Helpers UI ─────────────────────────────────────────────────────────────
function setStep(n, status, msg) {
  var dot = document.getElementById('d'+n);
  var desc = document.getElementById('s'+n);
  dot.className = 'dot ' + status;
  desc.className = 'step-desc ' + status;
  desc.textContent = msg;
  dot.textContent = status==='done'?'✓':status==='error'?'✗':status==='active'?'●':n;
}
function setP(v) { document.getElementById('progress').style.width = v+'%'; }

// ── Gerar Roteiro ──────────────────────────────────────────────────────────
async function gerarRoteiro() {
  var titulo = document.getElementById('titulo').value.trim();
  if(!titulo) { alert('Digite um título'); return; }
  var btn = document.getElementById('btn-roteiro');
  btn.disabled = true;
  btn.textContent = '⏳ Gerando roteiro...';
  document.getElementById('roteiro-preview').style.display = 'none';
  document.getElementById('btn-imagens').disabled = true;
  document.getElementById('btn-imagens').style.opacity = '.4';

  try {
    var resp = await fetch('/roteiro', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        titulo: titulo,
        contexto: document.getElementById('contexto').value,
        modelo: state.modelo,
        historias: state.historias,
        duracao: state.duracao,
        ritmo: state.ritmo
      })
    });
    var data = await resp.json();
    if(data.erro) throw new Error(data.erro);
    state.roteiro = data;
    state.prompts = (data.caso1&&data.caso1.prompts||[]).concat(data.caso2&&data.caso2.prompts||[]).concat(data.caso3&&data.caso3.prompts||[]).concat(data.prompts_final||[]);
    renderRoteiro(data);
    document.getElementById('btn-imagens').disabled = false;
    document.getElementById('btn-imagens').style.opacity = '1';
  } catch(e) {
    alert('Erro ao gerar roteiro: ' + e.message);
  }
  btn.disabled = false;
  btn.textContent = '📝 Gerar Roteiro';
}

function renderRoteiro(d) {
  // Ganchos
  var opts = [d.gancho_principal].concat(d.gancho_opcoes||[]);
  var ganchoHtml = opts.map(function(g,i){
    return '<div class="gancho-opt'+(i===0?' sel':'')+'" onclick="selOpt(this,\'gancho\')">'+esc(g)+'</div>';
  }).join('');
  document.getElementById('gancho-opts').innerHTML = ganchoHtml;

  // Narração
  var narracao = [d.gancho_principal]
    .concat(d.narracao_caso1||[])
    .concat(d.narracao_caso2||[])
    .concat([d.micro_promessa||''])
    .concat(d.narracao_caso3||[])
    .concat(d.narracao_final||[])
    .concat([d.frase_final_principal||''])
    .concat([d.pergunta_divisora_principal||''])
    .filter(Boolean).join(' ');
  document.getElementById('narracao-edit').value = narracao;

  // Prompts
  var promptsHtml = state.prompts.map(function(p,i){
    return '<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px">'
      +'<span style="background:#E8593C;color:#fff;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:700;flex-shrink:0;min-width:28px;text-align:center">'+(i+1)+'</span>'
      +'<div style="flex:1">'
        +'<textarea data-idx="'+i+'" style="width:100%;background:#111;border:1px solid #333;border-radius:6px;padding:8px;font-size:12px;color:#ccc;font-family:inherit;resize:none;height:60px" onchange="state.prompts['+i+']=this.value">'+esc(p)+'</textarea>'
        +'<div style="display:flex;gap:6px;margin-top:3px">'
          +'<button onclick="traduzirPrompt('+i+',this)" style="background:transparent;border:1px solid #333;border-radius:4px;padding:2px 8px;font-size:11px;color:#555;cursor:pointer;font-family:inherit">🌐 Traduzir</button>'
          +'<button onclick="regenPrompt('+i+')" style="background:#E8593C;color:#fff;border:none;border-radius:4px;padding:2px 8px;font-size:11px;cursor:pointer;font-family:inherit">↺ Regenerar</button>'
        +'</div>'
        +'<div id="trad-'+i+'" style="font-size:11px;color:#555;margin-top:3px;font-style:italic"></div>'
      +'</div>'
    +'</div>';
  }).join('');
  document.getElementById('prompts-list').innerHTML = promptsHtml;

  // Frase final
  var frases = [d.frase_final_principal].concat(d.frase_final_opcoes||[]);
  document.getElementById('frase-opts').innerHTML = frases.map(function(f,i){
    return '<div class="gancho-opt'+(i===0?' sel':'')+'" onclick="selOpt(this,\'frase\')">'+esc(f)+'</div>';
  }).join('');

  // Pergunta divisora
  var perguntas = [d.pergunta_divisora_principal].concat(d.pergunta_divisora_opcoes||[]);
  document.getElementById('pergunta-opts').innerHTML = perguntas.map(function(p,i){
    return '<div class="gancho-opt'+(i===0?' sel':'')+'" onclick="selOpt(this,\'pergunta\')">'+esc(p)+'</div>';
  }).join('');

  document.getElementById('roteiro-preview').style.display = 'block';
}

function selOpt(el, group) {
  el.closest('.gancho-opts').querySelectorAll('.gancho-opt').forEach(function(e){ e.classList.remove('sel'); });
  el.classList.add('sel');
}

async function traduzirPrompt(idx, btn) {
  btn.textContent = '...';
  try {
    var r = await fetch('/traduzir', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt: state.prompts[idx]})});
    var d = await r.json();
    document.getElementById('trad-'+idx).textContent = d.traducao || '';
  } catch(e) {}
  btn.textContent = '🌐 Traduzir';
}

async function regenPrompt(idx) {
  var textarea = document.querySelector('[data-idx="'+idx+'"]');
  var prompt = state.prompts[idx];
  var cell = document.getElementById('cell-'+idx);
  if(cell) { cell.style.opacity = '.4'; }
  try {
    var r = await fetch('/regenerar-imagem', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        session_id: state.sessionId,
        idx: idx,
        prompt: prompt,
        estilo: state.estilo,
        formato: state.formato
      })
    });
    var d = await r.json();
    if(d.ok && cell) {
      var img = cell.querySelector('img');
      if(img) img.src = '/imagem/'+state.sessionId+'/'+idx+'?t='+Date.now();
    }
  } catch(e) {}
  if(cell) cell.style.opacity = '1';
}

async function regenerarOpcoes(tipo) {
  var titulo = document.getElementById('titulo').value.trim();
  try {
    var r = await fetch('/regenerar-opcoes', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({titulo: titulo, tipo: tipo, modelo: state.modelo})
    });
    var d = await r.json();
    if(tipo === 'gancho') {
      document.getElementById('gancho-opts').innerHTML = d.opcoes.map(function(o,i){
        return '<div class="gancho-opt'+(i===0?' sel':'')+'" onclick="selOpt(this,\'gancho\')">'+esc(o)+'</div>';
      }).join('');
    } else if(tipo === 'frase') {
      document.getElementById('frase-opts').innerHTML = d.opcoes.map(function(o,i){
        return '<div class="gancho-opt'+(i===0?' sel':'')+'" onclick="selOpt(this,\'frase\')">'+esc(o)+'</div>';
      }).join('');
    } else {
      document.getElementById('pergunta-opts').innerHTML = d.opcoes.map(function(o,i){
        return '<div class="gancho-opt'+(i===0?' sel':'')+'" onclick="selOpt(this,\'pergunta\')">'+esc(o)+'</div>';
      }).join('');
    }
  } catch(e) {}
}

// ── Gerar Imagens e Áudio ──────────────────────────────────────────────────
async function gerarImagens() {
  var titulo = document.getElementById('titulo').value.trim();
  if(!state.roteiro) { alert('Gere o roteiro primeiro'); return; }

  // Coleta seleções do usuário
  var ganchoSel = document.querySelector('#gancho-opts .gancho-opt.sel');
  var fraseSel = document.querySelector('#frase-opts .gancho-opt.sel');
  var perguntaSel = document.querySelector('#pergunta-opts .gancho-opt.sel');
  var narracao = document.getElementById('narracao-edit').value;

  var payload = Object.assign({}, state.roteiro, {
    titulo: titulo,
    gancho: ganchoSel ? ganchoSel.textContent : state.roteiro.gancho_principal,
    frase_final: fraseSel ? fraseSel.textContent : state.roteiro.frase_final_principal,
    pergunta_divisora: perguntaSel ? perguntaSel.textContent : state.roteiro.pergunta_divisora_principal,
    narracao_custom: narracao,
    prompts_custom: state.prompts,
    estilo: state.estilo,
    formato: state.formato,
    modo_teste: state.modoTeste
  });

  document.getElementById('steps-card').style.display = 'block';
  document.getElementById('result-card').style.display = 'none';
  document.getElementById('btn-imagens').disabled = true;
  setP(5);
  setStep(1,'done','Roteiro aprovado'); setStep(2,'active','Aguardando...'); setStep(3,'','Aguardando...'); setStep(4,'','Aguardando...');

  try {
    var resp = await fetch('/gerar', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });

    var reader = resp.body.getReader();
    var dec = new TextDecoder();
    var buf = '';

    while(true) {
      var res = await reader.read();
      if(res.done) break;
      buf += dec.decode(res.value, {stream:true});
      var lines = buf.split('\n');
      buf = lines.pop();
      lines.forEach(function(line) {
        line = line.trim();
        if(!line.startsWith('data:')) return;
        try {
          var d = JSON.parse(line.slice(5));
          if(d.step) setStep(d.step, d.status, d.msg);
          if(d.progress) setP(d.progress);
          if(d.session_id) state.sessionId = d.session_id;
          if(d.zip) {
            document.getElementById('dl-btn').onclick = function(){ window.location='/download?file='+d.zip; };
            document.getElementById('result-card').style.display = 'block';
          }
          if(d.audio_url) {
            var ap = document.getElementById('audio-player');
            ap.src = d.audio_url;
            ap.style.display = 'block';
          }
          if(d.imgs_total) renderGrid(d.imgs_total);
          if(d.erro) alert('Erro: '+d.erro);
        } catch(e) {}
      });
    }
  } catch(e) { alert('Erro: '+e.message); }
  document.getElementById('btn-imagens').disabled = false;
}

function renderGrid(total) {
  var html = '';
  for(var i=0;i<total;i++){
    var num = String(i+1).padStart(2,'0');
    html += '<div class="img-cell" id="cell-'+i+'" onclick="openLightbox('+i+')">'
      +'<img src="/imagem/'+state.sessionId+'/'+i+'?t='+Date.now()+'" alt="IMG '+num+'" loading="lazy" onerror="this.style.display=\'none\'">'
      +'<span class="img-num">'+num+'</span>'
    +'</div>';
  }
  document.getElementById('img-grid').innerHTML = html;
}

function openLightbox(idx) {
  state.lbIdx = idx;
  var num = String(idx+1).padStart(2,'0');
  document.getElementById('lb-img').src = '/imagem/'+state.sessionId+'/'+idx+'?t='+Date.now();
  document.getElementById('lb-num').textContent = 'Imagem ' + num;
  document.getElementById('lb-prompt-text').textContent = state.prompts[idx] || '';
  document.getElementById('lb-prompt-edit').value = state.prompts[idx] || '';
  document.getElementById('lightbox').classList.add('open');
}

function closeLightbox() { document.getElementById('lightbox').classList.remove('open'); }

async function regenSingle() {
  var idx = state.lbIdx;
  var prompt = document.getElementById('lb-prompt-edit').value;
  state.prompts[idx] = prompt;
  var ta = document.querySelector('[data-idx="'+idx+'"]');
  if(ta) ta.value = prompt;
  closeLightbox();
  await regenPrompt(idx);
}

// ── Clonar ─────────────────────────────────────────────────────────────────
async function clonarRoteiro() {
  var transcricao = document.getElementById('transcricao').value.trim();
  var titulo = document.getElementById('titulo-clone').value.trim();
  if(!transcricao||!titulo) { alert('Preencha a transcrição e o título'); return; }
  document.getElementById('clone-result').textContent = 'Analisando estrutura...';
  try {
    var r = await fetch('/clonar', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        transcricao: transcricao,
        titulo: titulo,
        obs: document.getElementById('obs-clone').value,
        duracao: document.querySelector('[data-group="duracao-clone"].sel') ? document.querySelector('[data-group="duracao-clone"].sel').dataset.val : '50',
        estilo: document.querySelector('[data-group="estilo-clone"].sel') ? document.querySelector('[data-group="estilo-clone"].sel').dataset.val : 'stylized_game'
      })
    });
    var d = await r.json();
    if(d.erro) throw new Error(d.erro);
    document.getElementById('clone-result').textContent = 'Modelo detectado: ' + (d.modelo_identificado||'Animal');
    state.roteiro = d;
    state.prompts = (d.caso1&&d.caso1.prompts||[]).concat(d.caso2&&d.caso2.prompts||[]).concat(d.caso3&&d.caso3.prompts||[]).concat(d.prompts_final||[]);
    showTab('gerar', document.querySelector('.tab'));
    renderRoteiro(d);
    document.getElementById('btn-imagens').disabled = false;
    document.getElementById('btn-imagens').style.opacity = '1';
  } catch(e) {
    document.getElementById('clone-result').textContent = 'Erro: ' + e.message;
  }
}

// ── Calendário ─────────────────────────────────────────────────────────────
function addCalendario() {
  var titulo = document.getElementById('cal-titulo').value.trim();
  var data = document.getElementById('cal-data').value;
  if(!titulo) return;
  state.calendarioItems.push({titulo:titulo, data:data||'', status:'Planejado'});
  localStorage.setItem('calendario', JSON.stringify(state.calendarioItems));
  document.getElementById('cal-titulo').value = '';
  renderCalendario();
}

function renderCalendario() {
  var html = state.calendarioItems.map(function(item,i){
    return '<div class="cal-item">'
      +'<span class="cal-status cs-plan">'+item.status+'</span>'
      +'<span class="cal-title">'+esc(item.titulo)+'</span>'
      +'<span class="cal-date">'+item.data+'</span>'
      +'<button class="cal-btn" onclick="usarTitulo('+i+')">Gerar</button>'
    +'</div>';
  }).join('') || '<div style="color:#444;font-size:13px;padding:1rem">Nenhum vídeo planejado ainda.</div>';
  document.getElementById('cal-list').innerHTML = html;
}

function usarTitulo(idx) {
  var item = state.calendarioItems[idx];
  document.getElementById('titulo').value = item.titulo;
  showTab('gerar', document.querySelectorAll('.tab')[0]);
}

// ── Utils ──────────────────────────────────────────────────────────────────
function esc(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

document.getElementById('titulo').addEventListener('keydown', function(e){ if(e.key==='Enter') gerarRoteiro(); });
</script>
</body>
</html>"""

# ── Rotas ─────────────────────────────────────────────────────────────────────
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
