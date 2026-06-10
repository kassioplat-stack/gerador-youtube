import os, json, time, zipfile, requests, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)

CLAUDE_KEY     = os.environ.get("CLAUDE_API_KEY", "")
LEONARDO_KEY   = os.environ.get("LEONARDO_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "ArxqHrvFUTpvtCvw3KVh")
GROK_KEY = os.environ.get("GROK_API_KEY", "")

# Vozes fixas disponiveis
VOZES = [
    {"id": "ArxqHrvFUTpvtCvw3KVh", "nome": "Kássio"},
]

# Estilos visuais pre-programados para videos comerciais
ESTILOS_COMERCIAIS = [
    {"id": "realista", "nome": "Realista", "desc": "Fotorrealista, cinematografico, alta fidelidade"},
    {"id": "3d",       "nome": "3D",       "desc": "Render 3D moderno, luzes suaves, minimalista"},
    {"id": "desenho",  "nome": "Desenho",  "desc": "Ilustracao vetorial, linhas limpas, colorido"},
    {"id": "cinematic","nome": "Cinematic","desc": "Filmatico, cores ricas, profundidade de campo"},
]

sessions = {}

def limpar_sessions_antigas():
    try:
        agora = time.time()
        para_remover = [k for k, v in list(sessions.items())
                        if agora - (v.get('created_at', agora) if isinstance(v, dict) else agora) > 7200]
        for k in para_remover:
            sessions.pop(k, None)
    except:
        pass

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

ESTILO_ANIMAL = (
    "hand-drawn wildlife field journal illustration, "
    "naturalist notebook aesthetic, "
    "authentic pen-and-pencil sketch, "
    "fine black ink outlines, "
    "visible loose pencil construction lines, "
    "rough crosshatching, "
    "detailed wildlife documentary drawing, "
    "soft watercolor washes, "
    "earth-tone color palette, "
    "subtle natural colors, "
    "field researcher sketchbook style, "
    "scientific expedition journal, "
    "organic brush textures, "
    "highly detailed animal anatomy, "
    "natural environment, "
    "wide cinematic composition, "
    "storytelling illustration, "
    "soft natural lighting, "
    "museum-quality naturalist artwork, "
    "single scene only, "
    "no text, "
    "no labels, "
    "no collage, "
    "no multiple studies, "
    "no repeated animals, "
    "no border sketches"
)

ESTILOS = {"field_journal": ESTILO_ANIMAL}

FORMATOS = {
    "9:16": {"width": 768, "height": 1344},
    "16:9": {"width": 1344, "height": 768},
    "1:1":  {"width": 1024, "height": 1024}
}

DURACOES = {"40": 40, "60": 60, "90": 90, "120": 120, "180": 180, "240": 240, "300": 300}
PALAVRAS  = {"40": 88, "60": 130, "90": 195, "120": 260, "180": 390, "240": 520, "300": 650}

def calc_frases(dur, nh):
    d = DURACOES.get(str(dur), 60)
    total = max(round(d / 3), nh * 4 + 4)
    if nh == 1:
        return {"caso1": round(total*0.70), "caso2": 0, "caso3": 0, "final": round(total*0.30)}
    elif nh == 2:
        return {"caso1": round(total*0.40), "caso2": round(total*0.40), "caso3": 0, "final": round(total*0.20)}
    else:
        return {"caso1": round(total*0.25), "caso2": round(total*0.20), "caso3": round(total*0.25), "final": round(total*0.30)}

def build_system_mente(duracao_s, total_palavras):
    frases_camada1 = max(round(duracao_s / 10), 3)
    frases_camada2 = max(round(duracao_s / 10), 3)
    frases_camada3 = max(round(duracao_s / 7), 4)
    frases_final = max(round(duracao_s / 18), 2)

    return (
        "MISSAO DO CANAL: Revelar o mecanismo psicologico oculto por tras de comportamentos humanos.\n"
        "Nao e autoajuda. Nao e motivacao. Nao e conselho.\n"
        "E expor o que esta acontecendo embaixo — o que o espectador nao ve, o que sua mente faz sem avisar.\n"
        "O espectador nao aprende algo novo. Ele RECONHECE algo que ja fazia sem saber o nome.\n\n"

        "A VOZ DO CANAL:\n"
        "Nao e terapeuta. Nao e professor. Nao e coach.\n"
        "E alguem que te conhece de verdade e esta te dizendo uma coisa que voce preferia nao ouvir.\n"
        "Fala como o povo fala — direto, sem rodeio, sem palavra bonita.\n"
        "As vezes uma palavra mais forte porque a situacao pede.\n"
        "O espectador precisa SENTIR a mensagem — nao entender academicamente.\n"
        "E uma conversa seria entre duas pessoas. Uma esta expondo o que a outra nao quer ver.\n\n"

        "PADRAO DE CANAL 10 MILHOES — 7 REGRAS INEGOCIAVEIS:\n\n"

        "REGRA 1 — GANCHO: UMA FERIDA SO\n"
        "Uma ferida unica. Direta. Sem contradicao. Sem segunda frase explicando a primeira.\n"
        "O espectador para porque SENTIU — nao porque entendeu.\n"
        "ERRADO: Voce nao sabe quanto vale. E pior — voce acha que sabe. (contradiz e confunde)\n"
        "CERTO: Voce nao sabe quanto vale — e prova isso toda vez que espera alguem te dizer.\n\n"

        "REGRA 2 — NOMEAR E MELHOR QUE EXPLICAR\n"
        "O canal de 10M nao explica o mecanismo — ele NOMEIA algo que o espectador sentia mas nao conseguia dizer.\n"
        "Precisa de pelo menos UMA frase assim por video — de preferencia na virada entre camada 2 e 3.\n"
        "ERRADO: isso e um padrao psicologico de dependencia de validacao externa\n"
        "CERTO: Nao e autoestima baixa. E terceirizacao.\n"
        "CERTO: Seu valor virou cotacao. Sobe quando te admiram. Desce quando te ignoram.\n"
        "CERTO: Voce nao tem referencia interna — so reflexo.\n\n"

        "REGRA 3 — CAMADA 2: UMA FRASE FORTE VALE MAIS QUE TRES MEDIAS\n"
        "Nao explica o mecanismo em tres angulos diferentes.\n"
        "Uma frase que corta. O espectador entende e fica perturbado — sem precisar de confirmacao.\n"
        "ERRADO: Aprovacao era seguranca. Rejeicao era perigo. Entao ele montou um sistema que consulta os outros antes de te dizer como se sentir.\n"
        "CERTO: Seu cerebro aprendeu isso antes de voce aprender a ler. E nao atualizou desde entao.\n\n"

        "REGRA 4 — FERIDA: CENA REAL, NAO GENERICA\n"
        "Amarra numa cena concreta que o espectador viveu essa semana, hoje, nessa relacao.\n"
        "Vai ate o fim. Nao solta. Nao generaliza de volta.\n"
        "ERRADO: as pessoas ao redor influenciam sua percepcao de valor\n"
        "CERTO: Essa pessoa que te criticou essa semana — ela nem te conhece de verdade. Mas voce deixou ela decidir por dias.\n\n"

        "REGRA 5 — FRASE REPETIDA: PROIBIDA\n"
        "NUNCA repetir a mesma frase no mesmo video.\n"
        "Mata o impacto. Se uma frase e forte, ela aparece uma vez — na posicao certa.\n\n"

        "REGRA 6 — PERGUNTA DIVISORA: UMA SO\n"
        "Nunca duas perguntas finais competindo.\n"
        "Escolhe a mais forte, a mais pessoal, a mais inescapavel — e deixa ela sozinha.\n"
        "ERRADO: terminar com duas perguntas diferentes\n"
        "CERTO: uma pergunta que divide em dois lados e fica na cabeca\n\n"

        "REGRA 7 — METAFORA COM PESO EMOCIONAL\n"
        "So entra metafora que carrega emocao. Se nao tem peso emocional, nao entra.\n"
        "ERRADO: instalacao antiga (sem peso emocional — soa como suporte tecnico)\n"
        "CERTO: seu valor virou cotacao (visual, concreto, pesa)\n"
        "CERTO: voce deixa qualquer um votar em quanto voce vale (humilhante de reconhecer)\n\n"

        "PROIBIDO — NUNCA USE:\n"
        "- Vocabulario de livro: bussola de identidade, circuito cognitivo, mecanismo de defesa\n"
        "- Tom de terapeuta: isso e um padrao aprendido, sua mente processa, e importante reconhecer\n"
        "- Tom de professor: ou seja, em outras palavras, portanto, isso significa que\n"
        "- Abstracoes sem imagem: ausencia de fonte propria, estrutura interna, nucleo identitario\n"
        "- Linguagem corporativa: calibrado, otimizado, avaliadores, gerenciado\n"
        "- Autoajuda: voce pode mudar, o primeiro passo e, acredite em voce\n"
        "- Aspas duplas dentro de qualquer frase\n"
        "- Repeticao de frases\n\n"

        "ESTRUTURA OBRIGATORIA — 3 CAMADAS DE UM UNICO COMPORTAMENTO:\n\n"

        "CAMADA 1 — O ESPELHO (" + str(frases_camada1) + " frases):\n"
        "Descreve o comportamento em segunda pessoa, especifico e reconhecivel.\n"
        "Cenas do cotidiano — WhatsApp, espelho, trabalho, relacoes.\n"
        "Sem julgamento. Sem explicacao ainda. So o espelho.\n"
        "O espectador pensa: isso e exatamente o que eu faco.\n\n"

        "CAMADA 2 — O MECANISMO (" + str(frases_camada2) + " frases):\n"
        "Revela a engrenagem por tras do comportamento em linguagem simples.\n"
        "Sem termos tecnicos. Uma frase forte vale mais que tres medias.\n"
        "Mostra que nao e fraqueza — e como o cerebro foi montado.\n"
        "Termina com a NOMEACAO: uma frase que nomeia o que o espectador sentia sem conseguir dizer.\n\n"

        "MICRO-PROMESSA — entre camada 2 e 3:\n"
        "Uma frase que abre a ferida maior antes de entrar nela.\n"
        "NUNCA: o proximo passo e, agora veja, mas ha mais.\n"
        "CERTO: E o que isso faz com suas escolhas e mais serio do que parece.\n\n"

        "CAMADA 3 — A FERIDA (" + str(frases_camada3) + " frases):\n"
        "Conecta o mecanismo a algo pessoal, atual e inescapavel.\n"
        "Cena concreta — algo que ele fez essa semana, hoje, nessa relacao.\n"
        "Va ate o fim. Nao solte. Nao generalize de volta.\n"
        "Nao resolve. A ferida fica aberta. Ele nao consegue ignorar.\n\n"

        "EMOCAO-ANCORA:\n"
        "Uma emocao que atravessa as 3 camadas conectando tudo ao espectador.\n"
        "Nao e sobre o tema — e o que ele vai SENTIR ao se reconhecer.\n\n"

        "PERGUNTA INVISIVEL:\n"
        "A pergunta que o video responde sem nunca fazer em voz alta.\n"
        "Plantada no gancho, cresce nas camadas, explode na ferida.\n\n"

        "GANCHO — PRIMEIRA FRASE:\n"
        "Uma ferida so. Direta. Segunda pessoa. Planta divida emocional imediata.\n"
        "Zero apresentacao. Zero contexto. A primeira palavra ja e impacto.\n\n"

        "FRASE FINAL (" + str(frases_final) + " frases):\n"
        "Lenta. Filosofica. Nao resolve — aprofunda.\n"
        "Deixa uma pergunta sobre si mesmo — sem resposta, sem saida.\n\n"

        "PERGUNTA DIVISORA — UMA SO:\n"
        "A mais forte, a mais pessoal, a mais inescapavel.\n"
        "Divide em dois lados reais. Fica na cabeca.\n\n"

        "REGRAS TECNICAS:\n"
        "1. NUNCA repita a mesma frase — nem parecida\n"
        "2. NUNCA use aspas duplas dentro de qualquer texto\n"
        "3. Frases completas — sujeito, verbo, sentido\n"
        "4. Total: aproximadamente " + str(total_palavras) + " palavras\n"
        "5. Sem resolucao, sem conselho, sem saida\n\n"

        "Responda SOMENTE em JSON valido sem markdown:\n"
        "{\n"
        '  "comportamento": "nome curto do comportamento revelado",\n'
        '  "mecanismo": "nome em linguagem simples — como o povo fala",\n'
        '  "pergunta_invisivel": "pergunta que o video responde sem dizer em voz alta",\n'
        '  "emocao_ancora": "emocao que o espectador vai sentir ao se reconhecer",\n'
        '  "gancho_principal": "uma ferida so — segunda pessoa, impacto imediato, sem contradicao",\n'
        '  "gancho_opcoes": ["variacao2", "variacao3", "variacao4"],\n'
        '  "camada1": {"titulo": "O ESPELHO", "descricao": "o que o espectador faz", "twist": "o detalhe concreto que perturba"},\n'
        '  "camada2": {"titulo": "O MECANISMO", "descricao": "a engrenagem em linguagem simples", "twist": "a nomeacao — frase que nomeia o que ele sentia sem conseguir dizer"},\n'
        '  "camada3": {"titulo": "A FERIDA", "descricao": "cena concreta desta semana inescapavel", "twist": "o que nao da pra ignorar"},\n'
        '  "micro_promessa": "frase que abre ferida maior — nunca transicao mecanica",\n'
        '  "narracao_camada1": ["' + str(frases_camada1) + ' frases — espelho sem julgamento, cotidiano concreto, segunda pessoa"],\n'
        '  "narracao_camada2": ["' + str(frases_camada2) + ' frases — mecanismo simples, uma frase forte, termina com nomeacao impactante"],\n'
        '  "narracao_camada3": ["' + str(frases_camada3) + ' frases — ferida pessoal e atual, cena concreta, nao solta, nao generaliza"],\n'
        '  "narracao_final": ["' + str(frases_final) + ' frases — filosofica, sem resolucao, pergunta aberta"],\n'
        '  "frase_final_principal": "frase que fica na cabeca — sem resposta, sem saida",\n'
        '  "frase_final_opcoes": ["variacao2", "variacao3", "variacao4"],\n'
        '  "pergunta_divisora_principal": "uma so — a mais forte, a mais pessoal, divide em dois lados",\n'
        '  "pergunta_divisora_opcoes": ["variacao2", "variacao3", "variacao4"]\n'
        "}"
    )


def build_system(modelo, nh, dist, total_palavras):
    restricao = animais_recentes()
    restr = "Animais usados nos ultimos 7 dias - NAO repita: " + ", ".join(restricao) + "." if restricao else "Sem restricao de animais."

    if True:
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
        "11. TOTAL: aproximadamente " + str(total_palavras) + " palavras para TODA a narracao — respeite esse limite.\n"
        "12. CONGRUENCIA COM DURACAO: o roteiro e a narracao devem ser dimensionados EXATAMENTE para " + str(total_palavras) + " palavras — nem mais, nem menos. Um video de 40s nao pode ter narracao de 2 minutos.\n"
        "13. FIDELIDADE AO SCRIPT FINAL: a narracao gravada sera EXATAMENTE o texto gerado — gancho + corpo + frase final + pergunta divisora. Escreva cada frase como se ja estivesse sendo narrada. Nada sera editado antes de gravar.\n\n"

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

def parse_json_robusto(text):
    import re as _re, json as _json
    text = _re.sub(r"```json|```", "", text).strip()
    text = _re.sub(r",\s*([}\]])", r"\1", text)
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if m:
        text = m.group()
    try:
        return _json.loads(text)
    except _json.JSONDecodeError as e:
        def sanitizar_string(match):
            inner = match.group(1)
            inner = inner.replace('\\"', '__ESCAPED_QUOTE__')
            inner = inner.replace('"'  , "'")
            inner = inner.replace('__ESCAPED_QUOTE__', '\\"')
            return '"' + inner + '"'
        text2 = _re.sub(r'"((?:[^"\\]|\\.)*)"', sanitizar_string, text)
        try:
            return _json.loads(text2)
        except:
            last = text.rfind("}")
            if last > 0:
                try:
                    return _json.loads(text[:last+1])
                except:
                    pass
            raise

def chamar_claude(system, user_msg, max_tokens=6000, modelo="claude-sonnet-4-6"):
    for tentativa in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": modelo, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user_msg}]},
                timeout=300
            )
            resp = r.json()
            if "error" in resp:
                tipo = resp["error"].get("type", "unknown")
                msg = resp["error"].get("message", str(resp["error"]))
                raise Exception(f"API error [{tipo}]: {msg}")
            if "content" not in resp:
                raise Exception(f"Resposta inesperada da API: {str(resp)[:200]}")
            text = resp["content"][0]["text"]
            text = re.sub(r"```json|```", "", text).strip()
            text = re.sub(r',\s*([}\]])', r'\1', text)
            return text
        except Exception as e:
            if tentativa == 2:
                raise Exception(f"Claude erro: {str(e)}")
            time.sleep(5)

def leonardo_generate(prompt, formato="9:16", estilo="stylized_game", modelo="animais"):
    if modelo == "mente":
        sufixo = "3D render, matte blue rubber figure, minimalist, white background, studio lighting, clean composition, surreal psychology"
    else:
        sufixo = ESTILO_ANIMAL
    dims = FORMATOS.get(formato, FORMATOS["9:16"])
    for tentativa in range(3):
        try:
            prompt_final = (prompt + ", " + sufixo)[:1490]
            r = requests.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                headers={"authorization": f"Bearer {LEONARDO_KEY}", "content-type": "application/json"},
                json={"prompt": prompt_final, "modelId": "7b592283-e8a7-4c5a-9ba6-d18c31f258b9",
                      "width": dims["width"], "height": dims["height"], "num_images": 1,
                      "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text, humans, human hands, multiple animals, cartoon, anime, deformed", "guidance_scale": 7},
                timeout=40
            )
            data = r.json()
            print(f"LEONARDO RESPONSE: {str(data)[:300]}")
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
        except Exception as e:
            print(f"LEONARDO ERRO tentativa={tentativa+1}: {type(e).__name__}: {e}")
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
                json={'text': narracao_txt, 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability': 0.80, 'similarity_boost': 0.75, 'style': 0.0, 'use_speaker_boost': True}},
                timeout=60
            )
            if r.status_code == 200 and len(r.content) > 100:
                audio_data = r.content
                audio_service = 'ElevenLabs'
            else:
                print(f"ElevenLabs status={r.status_code} bytes={len(r.content)}")
    except Exception as e:
        print(f"ElevenLabs erro: {e}")

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
    duracao = str(data.get('duracao', '40'))
    total_palavras = PALAVRAS.get(duracao, 130)
    duracao_s = {"40":40,"60":60,"90":90,"120":120,"180":180,"240":240,"300":300}.get(duracao, 60)
    chars_limite = duracao_s * 13

    if modelo == 'mente':
        system = build_system_mente(duracao_s, total_palavras)
    else:
        nh = 3
        dist = calc_frases(duracao, nh)
        system = build_system(modelo, nh, dist, total_palavras)
    user_msg = f"Titulo: {titulo}\n\nLIMITE ABSOLUTO: a narracao completa deve ter NO MAXIMO {chars_limite} caracteres totais (equivale a {duracao_s} segundos de audio a 13 chars/segundo). Respeite rigorosamente."
    if contexto:
        user_msg += f"\nContexto: {contexto}"
    try:
        text = chamar_claude(system, user_msg)
        d = parse_json_robusto(text)
        if modelo == 'mente':
            d['_modelo'] = 'mente'
        else:
            animais = [d.get(k, {}).get('animal', '') for k in ['caso1', 'caso2', 'caso3'] if d.get(k, {}).get('animal')]
            if animais:
                salvar_historico(titulo, animais)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


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
    session_id = request.args.get('session_id', '')
    f = request.args.get('file', '')

    if session_id:
        s = sessions.get(session_id)
        if s and s.get('zip') and os.path.exists(s['zip']):
            return send_file(s['zip'], as_attachment=True, download_name='projeto_youtube.zip')
        f = f'/tmp/video_{session_id}.zip'

    if not f or not f.startswith('/tmp/'):
        return 'Nao encontrado', 404
    if not os.path.exists(f):
        return 'Arquivo nao encontrado', 404
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
    estilo = data.get('estilo', 'stylized_game')
    formato = data.get('formato', '9:16')
    modelo_req = data.get('modelo', 'animais')
    try:
        img = leonardo_generate(prompt, formato, estilo, modelo_req)
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

@app.route('/gerar-prompts', methods=['POST'])
def gerar_prompts():
    data = request.json
    script = data.get('script', '').strip()
    modelo = data.get('modelo', 'animais')
    formato = data.get('formato', '9:16')
    duracao_s = int(data.get('duracao', 60))

    n_prompts_req = data.get('n_prompts')
    if n_prompts_req:
        n_prompts = int(n_prompts_req)
    else:
        palavras = len(script.split())
        n_prompts = max(round(palavras * 0.45 / 2), 5)

    if modelo == 'mente':
        system_lines = [
            "Voce e o diretor de arte do canal de psicologia mais viral do YouTube.",
            "Sua missao: traduzir cada momento emocional da narracao em uma imagem impossivel, perturbadora e viciante.",
            "REGRA FUNDAMENTAL: cada prompt deve ser FIEL ao momento especifico da narracao — nao generico.",
            "Leia o script frase a frase. Identifique o sentimento central de cada momento. Traduza em imagem.",
            "Nao ilustre o que foi DITO — ilustre o que foi SENTIDO naquele momento.",
            "",
            "PERSONAGEM FIXO em TODOS os prompts:",
            "blue matte rubber 3D humanoid figure, genderless, faceless, smooth surface, two small black dot eyes, rounded head, white absolute background, soft studio lighting.",
            "",
            "4 DIRECOES VISUAIS — escolha a mais fiel ao sentimento do momento:",
            "SOMBRA REVELADORA: figura pequena, sombra enorme diferente dela revelando algo oculto",
            "CABECA ABERTA: topo da cabeca aberto com objeto metaforico do que esta sendo revelado",
            "DUPLO EU: duas figuras em conflito ou tensao representando o dilema do momento",
            "PSICOLOGIA SURREALISTA: figura com elemento impossivel que representa a verdade daquele momento",
            "",
            "PROIBIDO: texto na imagem, outros personagens, cenarios coloridos, fundo que nao seja branco absoluto.",
            "",
            "Gere EXATAMENTE " + str(n_prompts) + " prompts — distribuidos uniformemente pelo script.",
            "Cada prompt deve ser diferente e especifico para aquele momento da narracao.",
            'Retorne JSON sem markdown: {"prompts": ["prompt1", "prompt2"]}'
        ]
        system = "\n".join(system_lines)
    else:
        estilo_fixo = (
            "hand-drawn wildlife field journal illustration, "
            "naturalist notebook aesthetic, "
            "authentic pen-and-pencil sketch, "
            "fine black ink outlines, "
            "visible loose pencil construction lines, "
            "rough crosshatching, "
            "detailed wildlife documentary drawing, "
            "soft watercolor washes, "
            "earth-tone color palette, "
            "subtle natural colors, "
            "field researcher sketchbook style, "
            "scientific expedition journal, "
            "organic brush textures, "
            "highly detailed animal anatomy, "
            "natural environment, "
            "wide cinematic composition, "
            "storytelling illustration, "
            "soft natural lighting, "
            "museum-quality naturalist artwork, "
            "single scene only, "
            "no text, no labels, no collage, no multiple studies, no repeated animals, no border sketches"
        )
        system_lines = [
            "You are the art director of the most viral wildlife YouTube channel in the world.",
            "Your mission: translate EACH SENTENCE of the narration script into a precise, detailed visual scene.",
            "Every single word of the script must be reflected in the image — nothing generic, nothing invented.",
            "",
            "ABSOLUTE RULE — TOTAL FIDELITY TO THE SCRIPT:",
            "Read the script sentence by sentence. Identify the EXACT ACTION happening at that moment.",
            "If the script says 'the elephant stopped eating' — show the elephant standing still in front of untouched food.",
            "If the script says 'tourists hand bananas through car windows' — show exactly that scene.",
            "If the script says 'the cat ignores the rats' — show the cat sitting calmly while rats walk nearby.",
            "NEVER create a generic scene that could belong to any story.",
            "NEVER show an animal resting when the script describes action.",
            "The viewer must understand EXACTLY what is being narrated just by looking at the image.",
            "",
            "CONSISTENT CHARACTER PER ANIMAL:",
            "In the first prompt for each animal, define unique physical traits.",
            "Example: 'curious rhesus macaque with brown fur, bright amber eyes, sitting upright'",
            "Repeat those EXACT traits in every prompt for that same animal throughout its story.",
            "It is the same individual in different moments — not a generic animal.",
            "",
            "CAMERA ANGLE BY EMOTION:",
            "Introduction: wide establishing shot — animal in full environment, calm and curious.",
            "Tension: medium shot — something is off, viewer senses it.",
            "Escalation: dynamic mid-angle — action happening now, energy, movement.",
            "Twist: extreme close-up on eye or key detail — destabilizes the viewer.",
            "Philosophical ending: wide lonely shot — small animal in vast environment.",
            "",
            "LIGHTING BY NARRATIVE MOMENT:",
            "Opening: soft golden hour — false sense of safety.",
            "Tension: dramatic side shadows — something dark approaching.",
            "Twist/shock: high contrast or cold blue light — truth revealed.",
            "",
            "VISUAL STYLE — apply this EXACT style to every single prompt:",
            estilo_fixo,
            "",
            "MANDATORY PROMPT FORMAT:",
            "[unique physical description of animal] + [EXACT action from the script at this moment] + [camera angle] + [lighting] + [motion state: mid-motion / frozen / slow-blur]",
            "",
            "FORBIDDEN in any prompt: text in image, generic scenes, repeated poses, collage, multiple animal studies.",
            "",
            "Generate EXACTLY " + str(n_prompts) + " prompts — one per narrative moment, distributed evenly across the script.",
            "The sequence must form a complete visual story — someone watching only the images must understand the full narrative.",
            "",
            "ALSO return a Portuguese translation of each prompt for display to the user.",
            'Return JSON without markdown: {"prompts": [{"en": "english prompt", "pt": "descricao em portugues"}]}'
        ]
        system = "\n".join(system_lines)

    user_msg = (
        "Script (" + str(n_prompts) + " prompts needed):\n\n" + script +
        "\n\nGenerate " + str(n_prompts) + " prompts, one per narrative moment, strictly faithful to the script."
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=6000, modelo="claude-sonnet-4-6")
        d = parse_json_robusto(text)
        raw_prompts = d.get('prompts', [])
        # Normaliza formato: aceita lista de strings ou lista de {en, pt}
        prompts_en = []
        prompts_pt = []
        for p in raw_prompts:
            if isinstance(p, dict):
                prompts_en.append(p.get('en', ''))
                prompts_pt.append(p.get('pt', ''))
            else:
                prompts_en.append(str(p))
                prompts_pt.append(str(p))
        return jsonify({'prompts': prompts_en, 'prompts_pt': prompts_pt, 'total': len(prompts_en)})
    except Exception as e:
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
    system = (
        "Voce e um diretor de arte especialista em videos curtos virais do YouTube."
        " Recebera um prompt de imagem e deve gerar uma variacao melhorada do mesmo."
        " Mantenha o mesmo momento narrativo e o mesmo animal mas com angulo ou iluminacao diferente."
        " Mantenha as caracteristicas fisicas do animal identicas."
        " PROIBIDO: cinematic, realistic, documentary, photographic, an animal."
        " Retorne apenas o novo prompt em ingles, sem explicacoes."
    )
    try:
        text = chamar_claude(system, "Prompt atual:\n" + prompt_atual + "\n\nGere variacao melhorada.", max_tokens=300, modelo="claude-haiku-4-5-20251001")
        return jsonify({'prompt': text.strip().strip('"')})
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
        " Dado um titulo, gere um contexto criativo e especifico para guiar o roteiro."
        " Inclua: angulo emocional especifico, sugestao de animais ou casos, tom narrativo, elemento diferenciador."
        " Seja ESPECIFICO e CRIATIVO. Entre 2 e 4 frases diretas."
        " Retorne apenas o contexto em texto, sem explicacoes."
    )
    user_msg = "Titulo: " + titulo + "\nModelo: " + modelo + "\nDuracao: " + str(dur_s) + "s"
    if contexto_atual:
        user_msg += "\nContexto atual (gere variacao DIFERENTE): " + contexto_atual
    try:
        text = chamar_claude(system, user_msg, max_tokens=300, modelo="claude-haiku-4-5-20251001")
        return jsonify({'contexto': text.strip().strip('"')})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/score-viral', methods=['POST'])
def score_viral():
    data = request.json
    roteiro = data.get('roteiro', {})
    modelo = roteiro.get('_modelo', data.get('modelo', 'animais'))

    if modelo == 'mente':
        gancho = roteiro.get('gancho_principal', '')
        camada1 = roteiro.get('camada1', {})
        camada2 = roteiro.get('camada2', {})
        camada3 = roteiro.get('camada3', {})
        micro = roteiro.get('micro_promessa', '')
        frase_final = roteiro.get('frase_final_principal', '')
        pergunta_div = roteiro.get('pergunta_divisora_principal', '')
        narracao = ' '.join(
            roteiro.get('narracao_camada1', []) +
            roteiro.get('narracao_camada2', []) +
            roteiro.get('narracao_camada3', []) +
            roteiro.get('narracao_final', [])
        )
        system = (
            "Voce e especialista em canais virais de psicologia e comportamento humano no YouTube."
            " Avalie o roteiro em 6 dimensoes de 0 a 20 pontos. Seja rigoroso e especifico."
            " DIMENSOES:"
            " D1=FORCA DO GANCHO: planta divida emocional imediata? segunda pessoa direta? gera pergunta sobre si mesmo?"
            " D2=PROFUNDIDADE DO ESPELHO: espectador se reconhece na camada 1? e especifico ou generico? sem julgamento?"
            " D3=IMPACTO DO MECANISMO: camada 2 perturba e explica sem julgar? revela arquitetura cerebral? inescapavel?"
            " D4=INTENSIDADE DA FERIDA: camada 3 e pessoal e atual? amarra em situacao especifica inegavel? nao da pra negar?"
            " D5=PERGUNTA DIVISORA: divide em dois lados reais? pessoal? sem resposta obvia?"
            " D6=IMPACTO DA FRASE FINAL: e filosofica e lenta? deixa pergunta aberta sem resolver? fica na cabeca?"
            " Retorne EXATAMENTE neste formato sem desvios:"
            " TOTAL:XX"
            " D1:XX:justificativa em uma frase sem aspas duplas"
            " D2:XX:justificativa em uma frase sem aspas duplas"
            " D3:XX:justificativa em uma frase sem aspas duplas"
            " D4:XX:justificativa em uma frase sem aspas duplas"
            " D5:XX:justificativa em uma frase sem aspas duplas"
            " D6:XX:justificativa em uma frase sem aspas duplas"
            " FRACO:nome da dimensao mais fraca"
            " SUGESTAO:sugestao especifica de melhoria sem aspas duplas"
        )
        nomes = ["FORCA DO GANCHO","PROFUNDIDADE DO ESPELHO","IMPACTO DO MECANISMO","INTENSIDADE DA FERIDA","PERGUNTA DIVISORA","IMPACTO DA FRASE FINAL"]
        user_msg = (
            "GANCHO: " + gancho[:200] + "\n"
            "CAMADA 1 (ESPELHO): " + camada1.get('descricao','') + " twist: " + camada1.get('twist','') + "\n"
            "CAMADA 2 (MECANISMO): " + camada2.get('descricao','') + "\n"
            "CAMADA 3 (FERIDA): " + camada3.get('descricao','') + " twist: " + camada3.get('twist','') + "\n"
            "MICRO-PROMESSA: " + micro[:100] + "\n"
            "FRASE FINAL: " + frase_final[:150] + "\n"
            "PERGUNTA DIVISORA: " + pergunta_div[:150] + "\n"
            "NARRACAO: " + narracao[:600]
        )
    else:
        gancho = roteiro.get('gancho_principal', '')
        emocao = roteiro.get('emocao_ancora', '')
        pergunta_inv = roteiro.get('pergunta_invisivel', '')
        micro = roteiro.get('micro_promessa', '')
        caso1 = roteiro.get('caso1', {})
        caso2 = roteiro.get('caso2', {})
        caso3 = roteiro.get('caso3', {})
        frase_final = roteiro.get('frase_final_principal', '')
        pergunta_div = roteiro.get('pergunta_divisora_principal', '')
        narracao = ' '.join(
            roteiro.get('narracao_caso1', []) + roteiro.get('narracao_caso2', []) +
            roteiro.get('narracao_caso3', []) + roteiro.get('narracao_final', [])
        )
        system = (
            "Voce e especialista em canais virais do YouTube."
            " Avalie o roteiro em 5 dimensoes de 0 a 20 pontos. Seja rigoroso."
            " DIMENSOES:"
            " D1=FORCA DO GANCHO: vai direto sem apresentacao? gera pergunta imediata? tipo certo?"
            " D2=ESCALADA EMOCIONAL: caso1 menor que caso2 menor que caso3 em intensidade real? micro-promessa funciona?"
            " D3=QUALIDADE DO TWIST: impossivel de prever? chega em rafagas curtas? muda a percepcao?"
            " D4=PERGUNTA DIVISORA: divide em dois lados reais? pessoal? gera comentarios polarizados?"
            " D5=CONGRUENCIA NARRATIVA: pergunta invisivel plantada e respondida? emocao-ancora nos 3 casos?"
            " Retorne EXATAMENTE neste formato sem desvios:"
            " TOTAL:XX"
            " D1:XX:justificativa em uma frase sem aspas duplas"
            " D2:XX:justificativa em uma frase sem aspas duplas"
            " D3:XX:justificativa em uma frase sem aspas duplas"
            " D4:XX:justificativa em uma frase sem aspas duplas"
            " D5:XX:justificativa em uma frase sem aspas duplas"
            " FRACO:nome da dimensao mais fraca"
            " SUGESTAO:sugestao especifica de melhoria sem aspas duplas"
        )
        nomes = ["FORCA DO GANCHO","ESCALADA EMOCIONAL","QUALIDADE DO TWIST","PERGUNTA DIVISORA","CONGRUENCIA NARRATIVA"]
        user_msg = (
            "GANCHO: " + gancho[:200] + "\n"
            "EMOCAO: " + emocao + "\n"
            "PERGUNTA INVISIVEL: " + pergunta_inv + "\n"
            "CASO1: " + caso1.get('animal','') + " twist: " + caso1.get('twist','')[:100] + "\n"
            "CASO2: " + caso2.get('animal','') + " twist: " + caso2.get('twist','')[:100] + "\n"
            "CASO3: " + caso3.get('animal','') + " twist: " + caso3.get('twist','')[:100] + "\n"
            "MICRO-PROMESSA: " + micro[:100] + "\n"
            "FRASE FINAL: " + frase_final[:150] + "\n"
            "PERGUNTA DIVISORA: " + pergunta_div[:150] + "\n"
            "NARRACAO: " + narracao[:600]
        )

    try:
        text = chamar_claude(system, user_msg, max_tokens=800, modelo="claude-sonnet-4-6")
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        total = 0
        dimensoes = []
        ponto_fraco = ''
        sugestao = ''
        for line in lines:
            if line.startswith('TOTAL:'):
                try: total = int(line.split(':')[1].strip())
                except: pass
            elif line.startswith('D') and ':' in line:
                parts = line.split(':', 2)
                if len(parts) == 3:
                    idx_d = int(parts[0][1:]) - 1
                    score = 0
                    try: score = int(parts[1].strip())
                    except: pass
                    justificativa = parts[2].strip()
                    nome = nomes[idx_d] if 0 <= idx_d < len(nomes) else parts[0]
                    dimensoes.append({'nome': nome, 'score': score, 'justificativa': justificativa})
            elif line.startswith('FRACO:'):
                fraco_raw = line[6:].strip()
                import re as _re
                m = _re.match(r'^D(\d+)$', fraco_raw)
                if m and dimensoes:
                    idx_fraco = int(m.group(1)) - 1
                    fraco_raw = dimensoes[idx_fraco]['nome'] if 0 <= idx_fraco < len(dimensoes) else fraco_raw
                ponto_fraco = fraco_raw
            elif line.startswith('SUGESTAO:'):
                sugestao = line[9:].strip()
        if not total and dimensoes:
            total = sum(d['score'] for d in dimensoes)
        if not ponto_fraco and dimensoes:
            ponto_fraco = min(dimensoes, key=lambda d: d['score'])['nome']
        return jsonify({'total': total, 'dimensoes': dimensoes, 'ponto_fraco': ponto_fraco, 'sugestao': sugestao})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/corrigir-dimensao', methods=['POST'])
def corrigir_dimensao():
    data = request.json
    roteiro = data.get('roteiro', {})
    modelo = data.get('modelo', 'animais')
    dimensao = data.get('dimensao', '')
    justificativa = data.get('justificativa', '')
    sugestao = data.get('sugestao', '')

    if modelo == 'mente':
        contexto_modelo = (
            "Este e um roteiro do modelo MENTE — psicologia e comportamento humano.\n"
            "Narracao em segunda pessoa direta. 3 camadas: O Espelho, O Mecanismo, A Ferida.\n"
            "Sem citacoes cientificas formais. Ferida aberta no final sem resolucao.\n"
        )
        campos_disponiveis = (
            "gancho_principal, gancho_opcoes, camada1, camada2, camada3, "
            "micro_promessa, narracao_camada1, narracao_camada2, narracao_camada3, "
            "narracao_final, frase_final_principal, frase_final_opcoes, "
            "pergunta_divisora_principal, pergunta_divisora_opcoes"
        )
    else:
        contexto_modelo = (
            "Este e um roteiro do modelo ANIMAL — comportamento animal em escalada.\n"
            "Narracao em terceira pessoa. 3 casos: Interessante, Surpreendente, Chocante.\n"
        )
        campos_disponiveis = (
            "gancho_principal, gancho_opcoes, caso3, micro_promessa, narracao_caso3, "
            "narracao_final, frase_final_principal, frase_final_opcoes, "
            "pergunta_divisora_principal, pergunta_divisora_opcoes"
        )

    system = (
        "Voce e especialista em roteiros virais para YouTube.\n"
        + contexto_modelo +
        "Recebera um roteiro e um problema especifico. Corrija APENAS os campos necessarios.\n"
        "NAO altere o que nao foi solicitado. Preserve o estilo e estrutura geral.\n"
        "Campos disponiveis: " + campos_disponiveis + ".\n\n"
        "FORMATO DE RESPOSTA OBRIGATORIO — retorne APENAS linhas no formato:\n"
        "CAMPO:valor\n"
        "Para arrays (listas), use pipe como separador: CAMPO:item1|item2|item3\n"
        "Para objetos (camada1, caso3), use JSON simples em uma linha.\n"
        "NAO use aspas duplas fora do JSON de objetos.\n"
        "Exemplo:\n"
        "gancho_principal:Voce faz isso toda vez sem perceber\n"
        "gancho_opcoes:Sua mente te engana agora|Isso que voce chama de escolha nao e sua|Voce repete o mesmo erro de forma diferente\n"
        "camada3:{titulo:A FERIDA,descricao:A implicacao pessoal,twist:O que nao da pra negar}\n"
        "narracao_camada3:Voce sabe que faz isso.|E nao e fraqueza.|E o mecanismo que te protege de algo maior.\n"
    )
    user_msg = (
        "ROTEIRO:\n" + json.dumps(roteiro, ensure_ascii=False)[:2000] +
        "\n\nDIMENSAO: " + dimensao +
        "\nPROBLEMA: " + justificativa +
        "\nSUGESTAO: " + sugestao +
        "\n\nCorrija apenas o necessario. Retorne so os campos que mudaram."
    )
    try:
        text = chamar_claude(system, user_msg, max_tokens=2000, modelo="claude-sonnet-4-6")
        result = {}
        for line in text.strip().split('\n'):
            line = line.strip()
            if ':' not in line:
                continue
            campo, _, valor = line.partition(':')
            campo = campo.strip()
            valor = valor.strip()
            if not campo or not valor:
                continue
            if '|' in valor and not valor.startswith('{'):
                result[campo] = [v.strip() for v in valor.split('|') if v.strip()]
            elif valor.startswith('{'):
                try:
                    result[campo] = parse_json_robusto(valor)
                except:
                    result[campo] = valor
            elif campo.startswith('narracao_'):
                result[campo] = [v.strip() for v in valor.split('|') if v.strip()]
            else:
                result[campo] = valor
        return jsonify(result)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/gerar-thumbnails', methods=['POST'])
def gerar_thumbnails():
    data = request.json
    roteiro = data.get('roteiro', {})
    script = data.get('script', '')
    formato = data.get('formato', '9:16')
    estilo = data.get('estilo', 'stylized_game')
    caso3 = roteiro.get('caso3', {})
    caso1 = roteiro.get('caso1', {})
    system = (
        "Voce e especialista em thumbnails virais para YouTube."
        " Gere 3 conceitos de thumbnail. ZERO texto na imagem."
        " Thumbnail 1 TENSAO MAXIMA: close extremo no animal do caso 3 no momento do twist."
        " Thumbnail 2 ESPELHO HUMANO: animal em comportamento mais humano do video."
        " Thumbnail 3 CURIOSIDADE VISUAL: cena ambigua que provoca pergunta visual."
        " FORMATO de cada prompt: [fisico unico do animal] + [cena exata] + [angulo] + [iluminacao] + [movimento]."
        " Prompts em INGLES."
        ' Retorne JSON: {"conceitos": [{"emocao": "string", "conceito": "string pt-br", "prompt": "string en"}]}'
    )
    user_msg = (
        "Animal caso1: " + caso1.get('animal','') +
        "\nAnimal caso3: " + caso3.get('animal','') +
        "\nTwist caso3: " + caso3.get('twist','') +
        "\nScript: " + script[:500]
    )
    try:
        text = chamar_claude(system, user_msg, max_tokens=1500, modelo="claude-sonnet-4-6")
        d = parse_json_robusto(text)
        return jsonify({'conceitos': d.get('conceitos', [])})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/gerar-thumbnail-imagem', methods=['POST'])
def gerar_thumbnail_imagem():
    data = request.json
    idx = data.get('idx', 0)
    prompt = data.get('prompt', '')
    formato = data.get('formato', '9:16')
    estilo = data.get('estilo', 'stylized_game')
    session_id = data.get('session_id', '')
    modelo_req = data.get('modelo', 'animais')
    try:
        img = leonardo_generate(prompt, formato, estilo, modelo_req)
        if session_id and session_id in sessions:
            if 'thumbnails' not in sessions[session_id]:
                sessions[session_id]['thumbnails'] = {}
            sessions[session_id]['thumbnails'][idx] = img
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
        'animais': 'Canal de comportamento animal — cenas cinematograficas de animais reais.',
        'mente': 'Canal de psicologia — personagem azul 3D neutro, fundo branco, metafora visual minimalista.',
        'geral': 'Canal generico de conteudo educativo viral.'
    }.get(canal, 'Canal generico')
    system = (
        "Voce e o maior analista de thumbnails do YouTube do mundo."
        " Analise a thumbnail com precisao cirurgica."
        " CONTEXTO DO CANAL: " + canal_ctx +
        " DIMENSOES (0-25 cada):"
        " 1. PARADA DE SCROLL: elemento dominante claro, contraste, ponto focal."
        " 2. HIERARQUIA VISUAL: caminho do olho claro, composicao, sem elementos competindo."
        " 3. GATILHO EMOCIONAL: emocao clara, intensidade, curiosidade ou choque."
        " 4. CONSISTENCIA DE CANAL: identidade visual reconhecivel, estilo coerente."
        " Diagnostico: teste dos 0.3s, hierarquia, gatilho, texto, diagnostico final."
        " Checklist: 5 perguntas sim/nao."
        " Titulos: 3 opcoes do mais viral ao menos."
        " Prompt de correcao completo em ingles para Leonardo."
        ' Retorne JSON: {"total":0-100,"dimensoes":[{"nome":"string","score":0-25,"justificativa":"string"}],'
        '"diagnostico":"string","checklist":[{"pergunta":"string","ok":true}],'
        '"titulos":["t1","t2","t3"],"prompt_correcao":"string","ponto_fraco":"string","sugestao":"string"}'
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 2000,
                "system": system,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": imagem_b64}},
                    {"type": "text", "text": "Avalie esta thumbnail."}
                ]}]
            },
            timeout=30
        )
        text = r.json()['content'][0]['text']
        d = parse_json_robusto(text)
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
    system = (
        "Voce e especialista em thumbnails virais do YouTube."
        " Recebera um prompt e um problema especifico. Atualize o prompt para corrigir aquela dimensao."
        " Mantenha tudo que ja estava bom. Retorne apenas o prompt atualizado em ingles."
    )
    user_msg = "PROMPT: " + prompt_atual + "\nPROBLEMA: " + dimensao + " - " + justificativa + "\nAtualize o prompt."
    try:
        text = chamar_claude(system, user_msg, max_tokens=500, modelo="claude-sonnet-4-6")
        return jsonify({'prompt_atualizado': text.strip().strip('"')})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/audio-gerar', methods=['POST'])
def audio_gerar():
    try:
        data = request.get_json(force=True, silent=True) or {}
        texto = data.get('script', '').strip()
        if not texto:
            return jsonify({'erro': 'Script vazio'}), 400
        import uuid
        sid = str(uuid.uuid4())
        sessions[sid] = {'audio': None, 'imagens': {}, 'prompts': [], 'created_at': time.time()}
        print(f"AUDIO GERAR: voice={ELEVENLABS_VOICE} chars={len(texto)}")
        audio_data, servico = gerar_audio(texto, sid)
        if not audio_data:
            return jsonify({'erro': 'ElevenLabs nao retornou audio. Verifique seus creditos.'}), 500
        sessions[sid]['audio'] = audio_data
        print(f"AUDIO GERAR: OK servico={servico} bytes={len(audio_data)}")
        return jsonify({'ok': True, 'session_id': sid})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@app.route('/imagens-gerar', methods=['POST'])
def imagens_gerar():
    """Inicia geração de imagens em background. Retorna session_id imediatamente."""
    import uuid, threading
    data = request.get_json(force=True, silent=True) or {}
    prompts = data.get('prompts', [])
    narracao_session_id = data.get('narracao_session_id', '')
    formato = data.get('formato', '9:16')
    modelo_req = data.get('modelo', 'animais')

    if not prompts:
        return jsonify({'erro': 'Nenhum prompt enviado'}), 400

    sid = str(uuid.uuid4())
    sessions[sid] = {
        'imagens': {},
        'prompts': prompts,
        'audio': None,
        'created_at': time.time(),
        'status': 'gerando',
        'total': len(prompts),
        'erros': [],
        'zip': None,
    }

    # Recupera áudio já gerado antes de iniciar thread
    audio_data = None
    if narracao_session_id:
        s = sessions.get(narracao_session_id)
        if s and s.get('audio'):
            audio_data = s['audio']
        else:
            audio_path = f'/tmp/narracao_{narracao_session_id}.mp3'
            if os.path.exists(audio_path):
                with open(audio_path, 'rb') as fa:
                    audio_data = fa.read()

    def gerar_em_background(sid, prompts, formato, modelo_req, audio_data):
        import sys
        from concurrent.futures import ThreadPoolExecutor, as_completed
        print(f"THREAD INICIO: sid={sid} total={len(prompts)} modelo={modelo_req}", flush=True)

        def gerar_uma(args):
            i, prompt = args
            print(f"GERANDO IMAGEM {i+1}/{len(prompts)}", flush=True)
            img = leonardo_generate(prompt, formato, 'field_journal', modelo_req)
            print(f"IMAGEM {i+1} OK bytes={len(img)}", flush=True)
            return i, img

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(gerar_uma, (i, p)): i for i, p in enumerate(prompts)}
            for future in as_completed(futures):
                try:
                    i, img = future.result()
                    sessions[sid]['imagens'][i] = img
                    with open(f'/tmp/{sid}_{i}.jpg', 'wb') as f_img:
                        f_img.write(img)
                except Exception as e:
                    i = futures[future]
                    sessions[sid]['erros'].append(str(i + 1))
                    print(f"IMAGEM {i+1} ERRO: {type(e).__name__}: {e}", flush=True)

        # Monta ZIP ao final
        zip_path = f'/tmp/video_{sid}.zip'
        try:
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for i, img in sessions[sid]['imagens'].items():
                    zf.writestr(f'IMG_{str(i+1).zfill(2)}.jpg', img)
                if audio_data:
                    zf.writestr('narracao.mp3', audio_data)
                prompts_txt = '\n\n'.join([f"IMG {str(i+1).zfill(2)}:\n{p}" for i, p in enumerate(prompts)])
                zf.writestr('prompts.txt', prompts_txt.encode('utf-8'))
            sessions[sid]['zip'] = zip_path
        except Exception as e:
            print(f"ZIP ERRO: {e}")

        sessions[sid]['status'] = 'concluido'
        print(f"IMAGENS: concluido sid={sid} ok={len(sessions[sid]['imagens'])}/{len(prompts)}")

    thread = threading.Thread(target=gerar_em_background, args=(sid, prompts, formato, modelo_req, audio_data), daemon=False)
    thread.start()

    return jsonify({
        'ok': True,
        'session_id': sid,
        'total': len(prompts),
    })


@app.route('/imagens-status/<session_id>')
def imagens_status(session_id):
    """Polling: retorna quantas imagens já foram geradas e se o ZIP está pronto."""
    s = sessions.get(session_id)
    if not s:
        return jsonify({'erro': 'Sessao nao encontrada'}), 404
    return jsonify({
        'status': s.get('status', 'gerando'),
        'imagens_ok': len(s.get('imagens', {})),
        'total': s.get('total', 0),
        'erros': s.get('erros', []),
        'zip': s.get('zip'),
    })



# ─────────────────────────────────────────────
# ROTAS VIDEOS COMERCIAIS
# ─────────────────────────────────────────────

@app.route('/comercial-config', methods=['GET'])
def comercial_config():
    """Retorna vozes e estilos disponiveis."""
    return jsonify({'vozes': VOZES, 'estilos': ESTILOS_COMERCIAIS})


@app.route('/comercial-roteiro', methods=['POST'])
def comercial_roteiro():
    """Claude gera roteiro de cenas para video comercial."""
    data = request.get_json(force=True, silent=True) or {}
    titulo     = data.get('titulo', '').strip()
    segmento   = data.get('segmento', '').strip()
    estilo_id  = data.get('estilo', 'realista')
    descricao  = data.get('descricao', '').strip()
    n_cenas    = int(data.get('n_cenas', 6))

    estilo_obj = next((e for e in ESTILOS_COMERCIAIS if e['id'] == estilo_id), ESTILOS_COMERCIAIS[0])

    system = (
        "Voce e um diretor criativo especialista em videos comerciais virais para redes sociais."
        " Cria videos de ate 60 segundos para qualquer tipo de negocio — local ou digital."
        " Seu trabalho: gerar um roteiro dividido em cenas, onde cada cena tem 8-10 segundos."
        " Cada cena precisa de:"
        " 1. narracao: texto falado nessa cena (curto, impactante, em portugues)"
        " 2. descricao_visual: o que aparece visualmente nessa cena (em portugues, detalhado)"
        " 3. prompt_imagem: prompt em INGLES para gerar a imagem dessa cena no Leonardo AI"
        " 4. comando_video: instrucao em portugues do movimento/animacao do video dessa cena (ex: camera aproxima lentamente, zoom out revelando o ambiente)"
        " ESTILO VISUAL: " + estilo_obj['nome'] + " — " + estilo_obj['desc'] +
        " REGRAS:"
        " - Narracao total deve ter no maximo 120 palavras (60 segundos)"
        " - Cada cena deve ser visual e emocionalmente diferente da anterior"
        " - Comece com um gancho visual forte na cena 1"
        " - Termine com call-to-action claro na ultima cena"
        " - prompt_imagem sempre em ingles, detalhado, sem mencionar estilo (e aplicado automaticamente)"
        " Retorne SOMENTE JSON valido sem markdown:"
        ' {"titulo": "string", "cenas": [{"numero": 1, "narracao": "string", "descricao_visual": "string", "prompt_imagem": "string em ingles", "comando_video": "string em portugues"}]}'
    )

    user_msg = "Titulo: " + titulo + "\nSegmento/Negocio: " + segmento + "\nDescricao/Ideia: " + descricao + "\nNumero de cenas: " + str(n_cenas)

    try:
        text = chamar_claude(system, user_msg, max_tokens=3000)
        d = parse_json_robusto(text)
        # Cria sessao para esse projeto comercial
        import uuid
        sid = 'com_' + str(uuid.uuid4())
        sessions[sid] = {'com_imagens': {}, 'com_videos': {}, 'com_audio': None, 'created_at': time.time()}
        d['session_id'] = sid
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/comercial-imagem', methods=['POST'])
def comercial_imagem():
    """Gera imagem de uma cena via Leonardo."""
    data = request.get_json(force=True, silent=True) or {}
    prompt    = data.get('prompt', '')
    estilo_id = data.get('estilo', 'realista')
    session_id= data.get('session_id', '')
    cena_idx  = int(data.get('cena_idx', 0))

    # Sufixo por estilo
    sufixos = {
        'realista':  'photorealistic, cinematic, 8k, sharp details, professional photography, natural lighting',
        '3d':        '3D render, modern style, soft studio lighting, clean composition, high quality render',
        'desenho':   'vector illustration, flat design, clean lines, vibrant colors, modern graphic style',
        'cinematic': 'cinematic film, anamorphic lens, rich colors, bokeh, dramatic lighting, movie still',
    }
    sufixo = sufixos.get(estilo_id, sufixos['realista'])
    prompt_final = (prompt + ', ' + sufixo)[:1490]

    try:
        dims = FORMATOS.get('9:16', {'width': 768, 'height': 1344})
        r = requests.post(
            'https://cloud.leonardo.ai/api/rest/v1/generations',
            headers={'authorization': f'Bearer {LEONARDO_KEY}', 'content-type': 'application/json'},
            json={'prompt': prompt_final, 'modelId': '7b592283-e8a7-4c5a-9ba6-d18c31f258b9',
                  'width': dims['width'], 'height': dims['height'], 'num_images': 1,
                  'negative_prompt': 'blurry, low quality, distorted, text, watermark', 'guidance_scale': 7},
            timeout=40
        )
        data_r = r.json()
        if 'sdGenerationJob' not in data_r:
            raise Exception(f'Leonardo erro: {data_r}')
        gen_id = data_r['sdGenerationJob']['generationId']
        for _ in range(50):
            time.sleep(3)
            r2 = requests.get(f'https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}',
                              headers={'authorization': f'Bearer {LEONARDO_KEY}'}, timeout=15)
            imgs = r2.json().get('generations_by_pk', {}).get('generated_images', [])
            if imgs:
                img_url = imgs[0]['url']
                img_data = requests.get(img_url, timeout=20).content
                # Salva em sessao
                if session_id and session_id in sessions:
                    if 'com_imagens' not in sessions[session_id]:
                        sessions[session_id]['com_imagens'] = {}
                    sessions[session_id]['com_imagens'][cena_idx] = img_data
                path = f'/tmp/com_{session_id}_{cena_idx}.jpg'
                with open(path, 'wb') as f:
                    f.write(img_data)
                return jsonify({'ok': True, 'url': f'/comercial-imagem-serve/{session_id}/{cena_idx}'})
        raise Exception('Timeout Leonardo')
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500


@app.route('/comercial-imagem-serve/<session_id>/<int:idx>')
def comercial_imagem_serve(session_id, idx):
    import io
    s = sessions.get(session_id, {})
    img = s.get('com_imagens', {}).get(idx)
    if img:
        return send_file(io.BytesIO(img), mimetype='image/jpeg')
    path = f'/tmp/com_{session_id}_{idx}.jpg'
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return 'Nao encontrado', 404


@app.route('/comercial-video-iniciar', methods=['POST'])
def comercial_video_iniciar():
    """Inicia geracao de video no Grok (image-to-video). Retorna request_id para polling."""
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get('session_id', '')
    cena_idx   = int(data.get('cena_idx', 0))
    comando    = data.get('comando', '').strip()
    prompt_img = data.get('prompt_imagem', '').strip()

    # Tenta usar imagem gerada como base (image-to-video)
    img_path = f'/tmp/com_{session_id}_{cena_idx}.jpg'
    image_b64 = None
    if os.path.exists(img_path):
        import base64
        with open(img_path, 'rb') as f:
            image_b64 = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()

    payload = {
        'model': 'grok-imagine-video',
        'prompt': comando if comando else prompt_img,
        'duration': 6,
        'resolution': '720p',
        'aspect_ratio': '9:16',
    }
    # Grok nao aceita base64 em image.url — so URL publica
    # Por enquanto gera text-to-video sem imagem de referencia
    # (image-to-video sera implementado quando houver CDN)

    try:
        import traceback
        r = requests.post(
            'https://api.x.ai/v1/videos/generations',
            headers={'Authorization': f'Bearer {GROK_KEY}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )
        print(f'GROK STATUS: {r.status_code}')
        print(f'GROK RESPONSE: {r.text[:300]}')
        d = r.json()
        if 'request_id' not in d:
            raise Exception(f'Grok erro: {d}')
        return jsonify({'ok': True, 'request_id': d['request_id']})
    except Exception as e:
        import traceback
        print(f'GROK ERRO: {traceback.format_exc()}')
        return jsonify({'ok': False, 'erro': str(e)}), 500


@app.route('/comercial-video-status/<request_id>')
def comercial_video_status(request_id):
    """Polling do status de geracao do video no Grok."""
    try:
        r = requests.get(
            f'https://api.x.ai/v1/videos/{request_id}',
            headers={'Authorization': f'Bearer {GROK_KEY}'},
            timeout=15
        )
        d = r.json()
        status = d.get('status', 'pending')
        video_url = d.get('video', {}).get('url', '') if status == 'done' else ''
        return jsonify({'status': status, 'video_url': video_url})
    except Exception as e:
        return jsonify({'status': 'error', 'erro': str(e)}), 500


@app.route('/comercial-video-baixar', methods=['POST'])
def comercial_video_baixar():
    """Baixa o video do Grok e salva em sessao."""
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get('session_id', '')
    cena_idx   = int(data.get('cena_idx', 0))
    video_url  = data.get('video_url', '')

    try:
        r = requests.get(video_url, timeout=60)
        video_data = r.content
        path = f'/tmp/com_video_{session_id}_{cena_idx}.mp4'
        with open(path, 'wb') as f:
            f.write(video_data)
        if session_id and session_id in sessions:
            if 'com_videos' not in sessions[session_id]:
                sessions[session_id]['com_videos'] = {}
            sessions[session_id]['com_videos'][cena_idx] = video_data
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500


@app.route('/comercial-narracao', methods=['POST'])
def comercial_narracao():
    """Gera narracao completa do video comercial."""
    data = request.get_json(force=True, silent=True) or {}
    texto      = data.get('texto', '').strip()
    voice_id   = data.get('voice_id', ELEVENLABS_VOICE)
    session_id = data.get('session_id', '')

    if not texto:
        return jsonify({'erro': 'Texto vazio'}), 400

    try:
        r = requests.post(
            f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
            headers={'xi-api-key': ELEVENLABS_KEY, 'content-type': 'application/json'},
            json={'text': texto, 'model_id': 'eleven_multilingual_v2',
                  'voice_settings': {'stability': 0.75, 'similarity_boost': 0.75}},
            timeout=60
        )
        if r.status_code == 200 and len(r.content) > 100:
            audio_data = r.content
            path = f'/tmp/com_narracao_{session_id}.mp3'
            with open(path, 'wb') as f:
                f.write(audio_data)
            if session_id and session_id in sessions:
                sessions[session_id]['com_audio'] = audio_data
            return jsonify({'ok': True, 'audio_url': f'/comercial-audio/{session_id}'})
        else:
            return jsonify({'erro': f'ElevenLabs status={r.status_code}'}), 500
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/comercial-audio/<session_id>')
def comercial_audio(session_id):
    import io
    s = sessions.get(session_id, {})
    audio = s.get('com_audio')
    if audio:
        return send_file(io.BytesIO(audio), mimetype='audio/mpeg')
    path = f'/tmp/com_narracao_{session_id}.mp3'
    if os.path.exists(path):
        return send_file(path, mimetype='audio/mpeg')
    return 'Nao encontrado', 404


@app.route('/comercial-download', methods=['POST'])
def comercial_download():
    """Monta ZIP com videos + narracao."""
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get('session_id', '')
    n_cenas    = int(data.get('n_cenas', 6))

    zip_path = f'/tmp/comercial_{session_id}.zip'
    try:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for i in range(n_cenas):
                v_path = f'/tmp/com_video_{session_id}_{i}.mp4'
                if os.path.exists(v_path):
                    zf.write(v_path, f'cena_{str(i+1).zfill(2)}.mp4')
            a_path = f'/tmp/com_narracao_{session_id}.mp3'
            if os.path.exists(a_path):
                zf.write(a_path, 'narracao.mp3')
        return jsonify({'ok': True, 'zip': zip_path})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/comercial-download-zip')
def comercial_download_zip():
    session_id = request.args.get('session_id', '')
    zip_path = f'/tmp/comercial_{session_id}.zip'
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, download_name='video_comercial.zip')
    return 'Nao encontrado', 404



@app.route('/comercial-gerar-prompt', methods=['POST'])
def comercial_gerar_prompt():
    """Claude gera prompt EN para Leonardo com base na descricao da cena e foto opcional."""
    data = request.get_json(force=True, silent=True) or {}
    desc     = data.get('desc', '').strip()
    narracao = data.get('narracao', '').strip()
    estilo_id= data.get('estilo', 'realista')
    foto_b64 = data.get('foto', None)

    estilo_obj = next((e for e in ESTILOS_COMERCIAIS if e['id'] == estilo_id), ESTILOS_COMERCIAIS[0])

    system = (
        "You are a professional prompt engineer for image generation (Leonardo AI)."
        " Generate a single, detailed image generation prompt in English."
        " The prompt must be faithful to the scene description and visual style."
        " Style: " + estilo_obj['nome'] + " — " + estilo_obj['desc'] + "."
        " Rules: describe subject, action, environment, lighting, angle, mood."
        " Do NOT mention style keywords (applied automatically)."
        " Return ONLY the prompt text, no explanation, no quotes."
    )

    user_parts = []
    if narracao:
        user_parts.append("Scene narration: " + narracao)
    if desc:
        user_parts.append("Visual description: " + desc)
    user_msg = "\n".join(user_parts) if user_parts else desc

    try:
        if foto_b64 and ',' in foto_b64:
            media_type = foto_b64.split(';')[0].replace('data:', '')
            img_data = foto_b64.split(',')[1]
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 400,
                    "system": system,
                    "messages": [{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                        {"type": "text", "text": user_msg + "\n\nGenerate the image prompt based on this reference photo and the scene description above."}
                    ]}]
                },
                timeout=30
            )
            prompt = r.json()['content'][0]['text'].strip().strip('"')
        else:
            prompt = chamar_claude(system, user_msg, max_tokens=400, modelo="claude-haiku-4-5-20251001").strip().strip('"')

        return jsonify({'prompt': prompt})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ─────────────────────────────────────────────
# ROTAS MONTAR VIDEO (menu Animal/YouTube)
# ─────────────────────────────────────────────

VIDEO_SESSIONS = {}  # sid -> {status, msg, path}

EFEITOS_VIDEO = ['zoom_in', 'zoom_out', 'pan_right', 'pan_left', 'pan_up', 'pan_down']

def aplicar_efeito_ffmpeg(img_path, out_path, efeito, duracao=8, w=768, h=1344):
    """Aplica efeito de movimento em uma imagem estática usando ffmpeg."""
    import subprocess, random

    fps = 24
    frames = duracao * fps

    if efeito == 'zoom_in':
        vf = f"scale=8000:-1,zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h},fps={fps}"
    elif efeito == 'zoom_out':
        vf = f"scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h},fps={fps}"
    elif efeito == 'pan_right':
        vf = f"scale=8000:-1,zoompan=z=1.3:x='iw/2-(iw/zoom/2)+on/{frames}*iw*0.1':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h},fps={fps}"
    elif efeito == 'pan_left':
        vf = f"scale=8000:-1,zoompan=z=1.3:x='iw/2-(iw/zoom/2)-on/{frames}*iw*0.1':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h},fps={fps}"
    elif efeito == 'pan_up':
        vf = f"scale=8000:-1,zoompan=z=1.3:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on/{frames}*ih*0.08':d={frames}:s={w}x{h},fps={fps}"
    else:  # pan_down
        vf = f"scale=8000:-1,zoompan=z=1.3:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-on/{frames}*ih*0.08':d={frames}:s={w}x{h},fps={fps}"

    cmd = [
        'ffmpeg', '-y', '-loop', '1', '-i', img_path,
        '-vf', vf,
        '-t', str(duracao), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast', out_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise Exception(f'ffmpeg erro: {result.stderr.decode()[:200]}')


@app.route('/montar-video', methods=['POST'])
def montar_video():
    """Inicia montagem do video em background. Retorna video_session_id."""
    import uuid, threading, random
    data = request.get_json(force=True, silent=True) or {}
    session_id          = data.get('session_id', '')
    narracao_session_id = data.get('narracao_session_id', '')
    total               = int(data.get('total', 0))
    formato             = data.get('formato', '9:16')

    if not session_id or not total:
        return jsonify({'erro': 'Dados insuficientes'}), 400

    vid_sid = str(uuid.uuid4())
    VIDEO_SESSIONS[vid_sid] = {'status': 'processando', 'msg': 'Iniciando...', 'path': None}

    dims = FORMATOS.get(formato, FORMATOS['9:16'])
    w, h = dims['width'], dims['height']

    def montar_em_background(vid_sid, session_id, narracao_session_id, total, w, h):
        import subprocess, random
        try:
            clips = []
            efeitos_disponiveis = EFEITOS_VIDEO.copy()
            random.shuffle(efeitos_disponiveis)

            for i in range(total):
                img_path = f'/tmp/{session_id}_{i}.jpg'
                if not os.path.exists(img_path):
                    # Tenta recuperar da sessão
                    s = sessions.get(session_id, {})
                    img_data = s.get('imagens', {}).get(i)
                    if img_data:
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                    else:
                        VIDEO_SESSIONS[vid_sid]['msg'] = f'Imagem {i+1} não encontrada — pulando'
                        continue

                efeito = efeitos_disponiveis[i % len(efeitos_disponiveis)]
                clip_path = f'/tmp/clip_{vid_sid}_{i}.mp4'
                VIDEO_SESSIONS[vid_sid]['msg'] = f'Animando cena {i+1}/{total} ({efeito})...'
                aplicar_efeito_ffmpeg(img_path, clip_path, efeito, duracao=8, w=w, h=h)
                clips.append(clip_path)

            if not clips:
                raise Exception('Nenhuma imagem disponível para montar')

            # Concatenar clips com fade entre eles
            VIDEO_SESSIONS[vid_sid]['msg'] = 'Concatenando cenas...'
            lista_path = f'/tmp/lista_{vid_sid}.txt'
            with open(lista_path, 'w') as f:
                for c in clips:
                    f.write(f"file '{c}'\n")

            video_sem_audio = f'/tmp/video_sem_audio_{vid_sid}.mp4'
            subprocess.run([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', lista_path, '-c', 'copy', video_sem_audio
            ], capture_output=True, timeout=300)

            # Adicionar narração
            audio_path = f'/tmp/narracao_{narracao_session_id}.mp3'
            video_final = f'/tmp/video_final_{vid_sid}.mp4'

            if os.path.exists(audio_path):
                VIDEO_SESSIONS[vid_sid]['msg'] = 'Adicionando narração...'
                subprocess.run([
                    'ffmpeg', '-y',
                    '-i', video_sem_audio,
                    '-i', audio_path,
                    '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac',
                    '-shortest', video_final
                ], capture_output=True, timeout=120)
            else:
                os.rename(video_sem_audio, video_final)

            VIDEO_SESSIONS[vid_sid]['status'] = 'pronto'
            VIDEO_SESSIONS[vid_sid]['msg'] = 'Vídeo pronto!'
            VIDEO_SESSIONS[vid_sid]['path'] = video_final
            print(f'VIDEO MONTADO: {video_final}')

        except Exception as e:
            import traceback
            print(f'VIDEO ERRO: {traceback.format_exc()}')
            VIDEO_SESSIONS[vid_sid]['status'] = 'erro'
            VIDEO_SESSIONS[vid_sid]['msg'] = str(e)

    thread = threading.Thread(
        target=montar_em_background,
        args=(vid_sid, session_id, narracao_session_id, total, w, h),
        daemon=False
    )
    thread.start()

    return jsonify({'ok': True, 'video_session_id': vid_sid})


@app.route('/montar-video-status/<vid_sid>')
def montar_video_status(vid_sid):
    s = VIDEO_SESSIONS.get(vid_sid, {'status': 'erro', 'msg': 'Sessão não encontrada'})
    return jsonify({'status': s['status'], 'msg': s['msg']})


@app.route('/baixar-video/<vid_sid>')
def baixar_video(vid_sid):
    s = VIDEO_SESSIONS.get(vid_sid, {})
    path = s.get('path')
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True, download_name='video_youtube.mp4', mimetype='video/mp4')
    return 'Vídeo não encontrado', 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
