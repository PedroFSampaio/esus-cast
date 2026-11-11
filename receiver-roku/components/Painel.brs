sub init()
    m.configuracao = m.top.FindNode("configuracao")
    m.quadros = m.top.FindNode("quadros")
    m.aviso = m.top.FindNode("aviso")
    m.dados = m.top.FindNode("dados")
    m.resultado = m.top.FindNode("resultado")
    m.botoes = m.top.FindNode("botoes")
    m.consulta = m.top.FindNode("consulta")
    m.limite = m.top.FindNode("limite")
    m.botoes.buttons = ["IP do Windows", "Porta", "Token da sessão", "Testar conexão", "Conectar"]
    m.botoes.ObserveField("buttonSelected", "selecionar")
    m.consulta.ObserveField("fire", "solicitarQuadro")
    m.limite.ObserveField("fire", "expirar")

    m.registro = CreateObject("roRegistrySection", "esus-cast")
    m.ip = m.registro.Read("ip")
    m.porta = m.registro.Read("porta")
    if m.porta = "" then m.porta = "8766"
    m.token = m.registro.Read("token")
    m.sequencia = 0
    relogio = CreateObject("roDateTime")
    m.inicio = relogio.AsSeconds().ToStr()
    m.pendente = invalid
    m.atual = invalid
    m.modo = ""
    m.espera = 2
    atualizarDados()
    m.botoes.SetFocus(true)
    if configuracaoValida() then conectar()
end sub

sub atualizarDados()
    ip = m.ip
    if ip = "" then ip = "pendente"
    token = "pendente"
    if m.token <> "" then token = "informado"
    m.dados.text = "Windows " + ip + "   |   Porta " + m.porta + "   |   Token " + token
end sub

sub selecionar()
    indice = m.botoes.buttonSelected
    if indice < 0 or indice > 4 then return
    if m.modo = "teste" then cancelar()
    m.resultado.text = ""

    if indice <= 2
        valores = [m.ip, m.porta, m.token]
        m.campo = indice
        dialogo = CreateObject("roSGNode", "StandardKeyboardDialog")
        dialogo.title = m.botoes.buttons[indice]
        dialogo.text = valores[indice]
        dialogo.buttons = ["Salvar", "Cancelar"]
        dialogo.ObserveField("buttonSelected", "editar")
        m.top.dialog = dialogo
    else if not configuracaoValida()
        m.resultado.text = "Informe IPv4, porta de 1 a 65535 e o token hexadecimal de 16 caracteres."
    else if indice = 3
        m.modo = "teste"
        m.resultado.text = "Testando o recebimento de um quadro..."
        solicitarQuadro()
    else
        conectar()
    end if
end sub

sub editar(evento as Object)
    dialogo = evento.GetRoSGNode()
    if evento.GetData() = 0
        texto = dialogo.text.Trim()
        if m.campo = 0 then m.ip = texto
        if m.campo = 1 then m.porta = texto
        if m.campo = 2 then m.token = LCase(texto)
        atualizarDados()
    end if
    dialogo.close = true
end sub

function caracteresValidos(valor as String, permitidos as String) as Boolean
    if Len(valor) = 0 then return false
    for i = 1 to Len(valor)
        if Instr(1, permitidos, Mid(valor, i, 1)) = 0 then return false
    end for
    return true
end function

function configuracaoValida() as Boolean
    partes = m.ip.Split(".")
    if partes.Count() <> 4 then return false
    for each parte in partes
        if Len(parte) > 3 or not caracteresValidos(parte, "0123456789") then return false
        octeto = Val(parte)
        if octeto > 255 then return false
        if Len(parte) > 1 and Left(parte, 1) = "0" then return false
    end for
    ' Aceita os endereços locais compatíveis com o servidor da prova de conceito.
    primeiro = Val(partes[0])
    segundo = Val(partes[1])
    redeLocal = primeiro = 10 or (primeiro = 172 and segundo >= 16 and segundo <= 31)
    redeLocal = redeLocal or (primeiro = 192 and segundo = 168) or (primeiro = 169 and segundo = 254)
    if not redeLocal then return false
    if Len(m.porta) > 5 or not caracteresValidos(m.porta, "0123456789") then return false
    if Left(m.porta, 1) = "0" then return false
    if Val(m.porta) < 1 or Val(m.porta) > 65535 then return false
    return Len(m.token) = 16 and caracteresValidos(m.token, "0123456789abcdef")
end function

sub conectar()
    m.modo = "reproducao"
    m.espera = 2
    m.configuracao.visible = false
    m.aviso.visible = true
    m.top.SetFocus(true)
    solicitarQuadro()
end sub

sub solicitarQuadro()
    if m.modo = "" or m.pendente <> invalid then return
    m.sequencia = m.sequencia + 1
    url = "http://" + m.ip + ":" + m.porta + "/frame.jpg?token=" + m.token
    url = url + "&v=" + m.inicio + "-" + m.sequencia.ToStr()
    quadro = CreateObject("roSGNode", "Poster")
    quadro.width = 1280
    quadro.height = 720
    quadro.loadDisplayMode = "scaleToFit"
    m.quadros.InsertChild(quadro, 0)
    m.pendente = quadro
    quadro.ObserveField("loadStatus", "quadroAtualizado")
    m.limite.control = "start"
    quadro.uri = url
end sub

sub quadroAtualizado(evento as Object)
    if m.pendente = invalid then return
    ' Observadores antigos podem ter deixado eventos na fila do renderizador.
    if not m.pendente.IsSameNode(evento.GetRoSGNode()) then return
    estado = evento.GetData()
    if estado = "failed"
        expirar()
    else if estado = "ready"
        m.limite.control = "stop"
        quadro = m.pendente
        quadro.UnobserveField("loadStatus")
        m.pendente = invalid
        if m.modo = "teste"
            m.quadros.RemoveChild(quadro)
            m.resultado.text = "Conexão OK. A Roku recebeu e abriu o JPEG."
            m.modo = ""
        else
            if m.atual <> invalid then m.quadros.RemoveChild(m.atual)
            m.atual = quadro
            m.aviso.visible = false
            m.espera = 2
            salvarConfiguracao()
            agendar(2)
        end if
    end if
end sub

sub salvarConfiguracao()
    if m.registro.Read("ip") = m.ip and m.registro.Read("porta") = m.porta and m.registro.Read("token") = m.token
        return
    end if
    m.registro.Write("ip", m.ip)
    m.registro.Write("porta", m.porta)
    m.registro.Write("token", m.token)
    m.registro.Flush()
end sub

sub expirar()
    if m.pendente = invalid then return
    modo = m.modo
    cancelar()
    if modo = "teste"
        m.resultado.text = "Sem quadro. Confira servidor, IP, porta, token e conectividade da rede."
    else if modo = "reproducao"
        m.modo = modo
        m.aviso.visible = true
        agendar(m.espera)
        m.espera = m.espera * 2
        if m.espera > 15 then m.espera = 15
    end if
end sub

sub agendar(segundos as Integer)
    m.consulta.duration = segundos
    m.consulta.control = "start"
end sub

sub cancelar()
    m.modo = ""
    m.consulta.control = "stop"
    m.limite.control = "stop"
    if m.pendente <> invalid
        m.pendente.UnobserveField("loadStatus")
        m.quadros.RemoveChild(m.pendente)
        m.pendente = invalid
    end if
    if m.atual <> invalid
        m.quadros.RemoveChild(m.atual)
        m.atual = invalid
    end if
end sub

function onKeyEvent(tecla as String, pressionada as Boolean) as Boolean
    if pressionada and tecla = "back" and not m.configuracao.visible
        cancelar()
        m.aviso.visible = false
        m.resultado.text = ""
        m.configuracao.visible = true
        m.botoes.SetFocus(true)
        return true
    end if
    return false
end function
