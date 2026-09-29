MESSAGES = {
    "INVALID_PDF": "O arquivo não é um PDF válido.",
    "NO_TEXT": "Não foi possível ler texto neste PDF, nem com OCR.",
    "OCR_UNAVAILABLE": "OCR indisponível: instale o Tesseract e o idioma português.",
    "LLM_INVALID_OUTPUT": "O modelo devolveu uma resposta inválida após novas tentativas.",
    "LLM_UNAVAILABLE": "Serviço de IA indisponível ou ANTHROPIC_API_KEY ausente.",
    "INTERNAL": "Erro interno ao processar este CV.",
}


class PipelineError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
        self.message = MESSAGES[code]
