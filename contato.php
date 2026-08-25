<?php
/**
 * Recebe o formulário de contato do site e envia por e-mail para a ACE.
 * O site é estático — este é o único ponto com processamento no servidor.
 * Responde sempre em JSON: {"ok":true} ou {"ok":false,"erro":"..."}.
 */

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

$DESTINO   = 'faleconosco@acecalculos.com.br';
// O remetente precisa ser do próprio domínio, senão o SPF reprova e a mensagem
// cai no spam. O e-mail de quem escreveu vai no Reply-To.
$REMETENTE = 'faleconosco@acecalculos.com.br';

function responde($dados, $codigo) {
    http_response_code($codigo);
    echo json_encode($dados, JSON_UNESCAPED_UNICODE);
    exit;
}
function falha($msg, $codigo) {
    responde(array('ok' => false, 'erro' => $msg), $codigo);
}
function campo($nome) {
    return isset($_POST[$nome]) ? trim($_POST[$nome]) : '';
}
// Quebra de linha em cabeçalho de e-mail é injeção — nunca deixar passar.
function cabecalho_seguro($v) {
    return str_replace(array("\r", "\n", "\0"), ' ', $v);
}
/**
 * Codifica texto para cabeçalho de e-mail (RFC 2047). Só codifica quando tem
 * acento; quebra em pedaços de no máximo 75 caracteres, como o padrão exige,
 * sem partir caractere multibyte no meio.
 */
function mime_cabecalho($texto) {
    $texto = cabecalho_seguro($texto);
    if (preg_match('/^[\x20-\x7E]*$/', $texto)) {
        return $texto; // ASCII puro: não precisa codificar
    }
    $partes = array();
    $atual  = '';
    $total  = mb_strlen($texto, 'UTF-8');
    for ($i = 0; $i < $total; $i++) {
        $ch = mb_substr($texto, $i, 1, 'UTF-8');
        // 45 bytes viram 60 em base64, e 60 + '=?UTF-8?B?' + '?=' cabe nos 75
        if (strlen($atual . $ch) > 45) {
            $partes[] = $atual;
            $atual = '';
        }
        $atual .= $ch;
    }
    if ($atual !== '') {
        $partes[] = $atual;
    }
    $saida = array();
    foreach ($partes as $parte) {
        $saida[] = '=?UTF-8?B?' . base64_encode($parte) . '?=';
    }
    return implode("\r\n ", $saida);
}

/**
 * Nome que aparece no From/Reply-To. Sem acento vai entre aspas (resolve
 * vírgula, parêntese e afins); com acento vira encoded-word, que não pode
 * ficar entre aspas.
 */
function nome_exibicao($texto) {
    $texto = cabecalho_seguro($texto);
    if (preg_match('/^[\x20-\x7E]*$/', $texto)) {
        return '"' . str_replace(array('\\', '"'), array('\\\\', '\\"'), $texto) . '"';
    }
    return mime_cabecalho($texto);
}

if (!isset($_SERVER['REQUEST_METHOD']) || $_SERVER['REQUEST_METHOD'] !== 'POST') {
    falha('Método não permitido.', 405);
}

// Campo-armadilha: fica fora da tela no formulário, então só robô preenche.
// Responde sucesso de propósito, para o robô não descobrir que foi barrado.
if (campo('website') !== '') {
    responde(array('ok' => true), 200);
}

$nome    = campo('nome');
$email   = campo('email');
$fone    = campo('whatsapp');
$msg     = campo('mensagem');
$digitos = preg_replace('/\D/', '', $fone);

if (mb_strlen($nome) < 2)                           falha('Informe o seu nome.', 422);
if (!filter_var($email, FILTER_VALIDATE_EMAIL))     falha('Informe um e-mail válido.', 422);
if (strlen($digitos) < 10 || strlen($digitos) > 11) falha('Informe o DDD + número.', 422);
if (mb_strlen($msg) < 3)                            falha('Escreva a sua mensagem.', 422);
if (mb_strlen($nome) > 120 || mb_strlen($msg) > 5000) {
    falha('Mensagem longa demais.', 422);
}

// Freio simples contra envio repetido do mesmo IP. Falha aberto de propósito:
// se não der para gravar o arquivo, o envio segue normalmente.
$ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '0.0.0.0';
$marca = sys_get_temp_dir() . '/ace_contato_' . md5($ip);
if (@file_exists($marca) && (time() - @filemtime($marca)) < 20) {
    falha('Aguarde alguns segundos antes de enviar de novo.', 429);
}
@touch($marca);

$fone_fmt = strlen($digitos) === 11
    ? '(' . substr($digitos, 0, 2) . ') ' . substr($digitos, 2, 5) . '-' . substr($digitos, 7)
    : '(' . substr($digitos, 0, 2) . ') ' . substr($digitos, 2, 4) . '-' . substr($digitos, 6);

$corpo = "Nova mensagem pelo formulário do site acecalculos.com.br\n"
       . "────────────────────────────────────────\n\n"
       . "Nome:      " . $nome . "\n"
       . "E-mail:    " . $email . "\n"
       . "WhatsApp:  +55 " . $fone_fmt . "\n"
       . "Recebido:  " . date('d/m/Y \à\s H:i') . "\n\n"
       . "Mensagem:\n"
       . $msg . "\n\n"
       . "────────────────────────────────────────\n"
       . "Responda este e-mail para falar direto com a pessoa.\n";

$cabecalhos = "From: " . nome_exibicao('ACE Cálculos (site)') . " <" . $REMETENTE . ">\r\n"
            . "Reply-To: " . nome_exibicao($nome) . " <" . cabecalho_seguro($email) . ">\r\n"
            . "MIME-Version: 1.0\r\n"
            . "Content-Type: text/plain; charset=UTF-8\r\n"
            . "Content-Transfer-Encoding: 8bit\r\n"
            . "X-Mailer: site-ace";

$assunto = mime_cabecalho('Contato pelo site — ' . $nome);

$enviado = @mail($DESTINO, $assunto, $corpo, $cabecalhos, '-f' . $REMETENTE);

if (!$enviado) {
    error_log('[contato.php] mail() falhou para ' . $DESTINO);
    falha('Não foi possível enviar agora. Escreva para faleconosco@acecalculos.com.br ou chame no (92) 99156-4219.', 500);
}

responde(array('ok' => true), 200);
