from core.nlp.asr_corrector import ASRCorrector

corrector = ASRCorrector()

test_phrases = [
    "астра в ключи спатифай",
    "паставь мая вална",
    "хадэ резка от крой",
    "запусти вин вс обход",
    "сделай па тиши на два цать",
    "пагода в калинингради",
    "чта такае маятник"
]

for phrase in test_phrases:
    fixed = corrector.correct(phrase)
    print(f"Vosk:  {phrase}")
    print(f"Fixed: {fixed}\n")