import os, json, time, zipfile, requests, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)

CLAUDE_KEY     = os.environ.get("CLAUDE_API_KEY", "")
LEONARDO_KEY   = os.environ.get("LEONARDO_API_KEY", "")
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "ArxqHrvFUTpvtCvw3KVh")

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

ESTILO_ANIMAL = (
    "hand-drawn naturalist field journal, black ink sketch, loose pencil lines, "
    "rough crosshatching, white background, watercolor accents, "
    "scientific notebook style, authentic hand-drawn illustration, "
    "no text, no labels, no typography"
)

# Mantido para compatibilidade — nao usado
ESTILOS = {"field_journal": ESTILO_ANIMAL}

FORMATOS = {
    "9:16": {"width": 768, "height": 1344},
    "16:9": {"width": 1344, "height": 768},
    "1:1":  {"width": 1024, "height": 1024}
}

DURACOES = {"40": 40, "60": 60, "90": 90, "120": 120, "180": 180, "240": 240, "300": 300}
PALAVRAS  = {"40": 88, "60": 130, "90": 195, "120": 260, "180": 390, "240": 520, "300": 650}

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

    # Modelo animais — unico modelo desta funcao (mente usa build_system_mente)
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
    # Limpa markdown
    text = _re.sub(r"```json|```", "", text).strip()
    # Remove trailing commas
    text = _re.sub(r",\s*([}\]])", r"\1", text)
    # Extrai bloco JSON
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if m:
        text = m.group()
    # Tenta parse direto
    try:
        return _json.loads(text)
    except _json.JSONDecodeError as e:
        # Estrategia: substitui aspas duplas dentro de valores string por aspas simples
        # Encontra strings JSON e sanitiza o conteudo interno
        def sanitizar_string(match):
            inner = match.group(1)
            # Remove aspas duplas do interior da string
            inner = inner.replace('\\"', '__ESCAPED_QUOTE__')
            inner = inner.replace('"'  , "'")
            inner = inner.replace('__ESCAPED_QUOTE__', '\\"')
            return '"' + inner + '"'
        text2 = _re.sub(r'"((?:[^"\\]|\\.)*)"', sanitizar_string, text)
        try:
            return _json.loads(text2)
        except:
            # Ultimo recurso: remove tudo apos o ultimo } valido
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
            # Detecta erro da API antes de tentar acessar content
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
            r = requests.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                headers={"authorization": f"Bearer {LEONARDO_KEY}", "content-type": "application/json"},
                json={"prompt": (prompt + ", " + sufixo)[:900], "width": dims["width"], "height": dims["height"], "num_images": 1, "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text, humans, cartoon, anime, deformed", "guidance_scale": 7},
                timeout=40
            )
            data = r.json()
            if "sdGenerationJob" not in data:
                raise Exception(f"Leonardo erro: {data}")
            gen_id = data["sdGenerationJob"]["generationId"]
            for poll_i in range(80):
                time.sleep(3)
                r2 = requests.get(f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                                  headers={"authorization": f"Bearer {LEONARDO_KEY}"}, timeout=15)
                r2_data = r2.json()
                gen_data = r2_data.get("generations_by_pk", {})
                status = gen_data.get("status", "")
                imgs = gen_data.get("generated_images", [])
                if imgs:
                    return requests.get(imgs[0]["url"], timeout=20).content
                if status == "FAILED":
                    raise Exception(f"Leonardo FAILED: {r2_data}")
                if poll_i == 0:
                    print(f"POLL STATUS: {status}, data: {str(r2_data)[:200]}")
            raise Exception(f"Timeout apos 240s. gen_id={gen_id}")
        except Exception as e:
            print(f"Leonardo tentativa {tentativa+1} erro: {str(e)[:200]}")
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
    duracao = str(data.get('duracao', '40'))
    total_palavras = PALAVRAS.get(duracao, 130)
    duracao_s = {"40":40,"60":60,"90":90,"120":120,"180":180,"240":240,"300":300}.get(duracao, 60)
    chars_limite = duracao_s * 13

    # MENTE tem estrutura e system prompt próprios
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
        # Salva historico — animais para Animal, comportamento para MENTE
        if modelo == 'mente':
            d['_modelo'] = 'mente'  # marca para o frontend
        else:
            animais = [d.get(k, {}).get('animal', '') for k in ['caso1', 'caso2', 'caso3'] if d.get(k, {}).get('animal')]
            if animais:
                salvar_historico(titulo, animais)
        return jsonify(d)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/narracao', methods=['POST'])

def gerar():
    limpar_sessions_antigas()
    data = request.json
    estilo = data.get('estilo', 'stylized_game')
    formato = data.get('formato', '9:16')
    prompts_custom = data.get('prompts_custom', [])
    narracao_custom = data.get('narracao_custom', '')
    narracao_session_id = data.get('narracao_session_id')
    so_audio = data.get('so_audio', False)

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
        print(f'STREAM: so_audio={so_audio}, prompts={len(prompts)}, narracao_session_id={narracao_session_id}')
        sessions[session_id] = {'imagens': {}, 'prompts': prompts, 'audio': None}
        yield 'data:' + json.dumps({'session_id': session_id, 'imgs_total': len(prompts)}) + '\n\n'
        # Modo so_audio — pula imagens e gera apenas audio
        if so_audio:
            try:
                audio_data, audio_service = gerar_audio(narracao_txt, session_id)
                sessions[session_id]['audio'] = audio_data
                if audio_data:
                    yield 'data:' + json.dumps({'audio_ok': True}) + '\n\n'
                else:
                    yield 'data:' + json.dumps({'erro': 'Falha ao gerar audio'}) + '\n\n'
            except Exception as e:
                yield 'data:' + json.dumps({'erro': str(e)}) + '\n\n'
            return
        yield 'data:' + json.dumps({'step': 1, 'status': 'done', 'msg': 'Prompts recebidos', 'progress': 15}) + '\n\n'

        yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': 'Gerando imagens...', 'progress': 18}) + '\n\n'
        erros = []
        for i, prompt in enumerate(prompts):
            num = str(i + 1).zfill(2)
            try:
                img = leonardo_generate(prompt, formato, estilo, modelo)
                sessions[session_id]['imagens'][i] = img
                img_path = f'/tmp/{session_id}_{i}.jpg'
                with open(img_path, 'wb') as f_img:
                    f_img.write(img)
                pct = 18 + int((i + 1) / max(len(prompts), 1) * 50)
                yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': f'Imagem {num}/{len(prompts)} ok', 'progress': pct, 'img_idx': i, 'imgs_total': len(prompts)}) + '\n\n'
            except Exception as e:
                erros.append(num)
                erro_msg = str(e)[:80]
                print(f"ERRO IMAGEM {num}: {erro_msg}")
                yield 'data:' + json.dumps({'step': 2, 'status': 'active', 'msg': f'Imagem {num} falhou: {erro_msg}', 'progress': 18 + int((i + 1) / max(len(prompts), 1) * 50)}) + '\n\n'

        msg_imgs = f"{len(sessions[session_id]['imagens'])}/{len(prompts)} imagens geradas"
        if erros:
            msg_imgs += f" (falharam: {', '.join(erros)})"
        yield 'data:' + json.dumps({'step': 2, 'status': 'done', 'msg': msg_imgs, 'progress': 70}) + '\n\n'

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
            yield 'data:' + json.dumps({'audio_ok': True, 'narracao_ok': True, 'audio_url': f'/audio/{session_id}'}) + '\n\n'

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
    session_id = request.args.get('session_id', '')
    f = request.args.get('file', '')
    if session_id:
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
    try:
        img = leonardo_generate(prompt, formato, estilo, modelo)
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

    # n_prompts vem do frontend (palavras * 0.45 / 2) ou calcula aqui
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
        system_lines = [
            "Voce e um diretor de arte especialista em videos curtos virais do YouTube.",
            "Sua missao: traduzir cada momento da narracao em uma imagem fiel ao script.",
            "REGRA FUNDAMENTAL: cada prompt deve ser FIEL ao momento especifico da narracao.",
            "Leia o script frase a frase. Identifique o que esta acontecendo. Traduza em imagem.",
            "",
            "ESTILO FIXO: Hand-drawn wildlife field journal, naturalist sketchbook, black ink sketch, white background.",
            "",
            "FORMATO: [animal especifico com caracteristicas fisicas] + [acao exata do momento] + [angulo] + [iluminacao].",
            "Defina o animal no primeiro prompt e repita as caracteristicas fisicas em todos os outros.",
            "Angulos: wide shot para apresentacao, close-up para tensao, extreme close-up para twist.",
            "PROIBIDO: cinematic, realistic, photographic, texto na imagem.",
            "",
            "Gere EXATAMENTE " + str(n_prompts) + " prompts — distribuidos uniformemente pelo script.",
            "Cada prompt diferente e especifico para aquele momento da narracao.",
            'Retorne JSON sem markdown: {"prompts": ["prompt1", "prompt2"]}'
        ]
        system = "\n".join(system_lines)

    user_msg = (
        "Script (" + str(n_prompts) + " prompts necessarios):\n\n" + script +
        "\n\nGere " + str(n_prompts) + " prompts em ingles, um por momento, fieis ao script."
    )

    try:
        text = chamar_claude(system, user_msg, max_tokens=4000, modelo="claude-sonnet-4-6")
        d = parse_json_robusto(text)
        prompts = d.get('prompts', [])
        return jsonify({'prompts': prompts, 'total': len(prompts)})
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
        # Score especifico para MENTE — 5 dimensoes corretas
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
        # Score Animal — dimensoes originais
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
                # Se Claude retornou D1/D2/etc em vez do nome, converte
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
        # Se ponto_fraco ainda vazio, usa a dimensao com menor score
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
        # Parse linha por linha
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
            # Arrays separados por pipe
            if '|' in valor and not valor.startswith('{'):
                result[campo] = [v.strip() for v in valor.split('|') if v.strip()]
            # Objetos JSON
            elif valor.startswith('{'):
                try:
                    result[campo] = parse_json_robusto(valor)
                except:
                    result[campo] = valor
            # Narracao como array (campo comeca com narracao_)
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
    try:
        img = leonardo_generate(prompt, formato, estilo, modelo)
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


@app.route('/testar-leonardo')
def testar_leonardo():
    try:
        # Passo 1: cria geracao
        r = requests.post(
            "https://cloud.leonardo.ai/api/rest/v1/generations",
            headers={"authorization": f"Bearer {LEONARDO_KEY}", "content-type": "application/json"},
            json={"prompt": "a cat sitting on a chair", "width": 512, "height": 512, "num_images": 1},
            timeout=30
        )
        data = r.json()
        gen_id = data.get("sdGenerationJob", {}).get("generationId")
        if not gen_id:
            return jsonify({"erro": "sem generationId", "response": data})
        # Passo 2: polling
        for i in range(20):
            time.sleep(3)
            r2 = requests.get(
                f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                headers={"authorization": f"Bearer {LEONARDO_KEY}"}, timeout=15
            )
            data2 = r2.json()
            gen_data = data2.get("generations_by_pk", {})
            status = gen_data.get("status", "unknown")
            imgs = gen_data.get("generated_images", [])
            if imgs:
                return jsonify({"ok": True, "tentativas": i+1, "url": imgs[0]["url"]})
            if status == "FAILED":
                return jsonify({"erro": "FAILED", "data": data2})
        return jsonify({"erro": "timeout", "ultimo_status": status, "data": data2})
    except Exception as e:
        return jsonify({"erro": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

