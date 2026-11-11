sub Main()
    porta = CreateObject("roMessagePort")
    tela = CreateObject("roSGScreen")
    tela.SetMessagePort(porta)
    tela.CreateScene("Painel")
    tela.Show()

    while true
        evento = wait(0, porta)
        if type(evento) = "roSGScreenEvent"
            if evento.IsScreenClosed() then return
        end if
    end while
end sub
