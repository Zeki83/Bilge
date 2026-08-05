#!/usr/bin/env python3
"""
Bilge OS - Response Templates

Bevat herbruikbare communicatierichtlijnen voor het Response System.

Deze module:
- bepaalt niet inhoudelijk wat Bilge antwoordt;
- levert richtlijnen voor toon, opening, structuur en afsluiting;
- ondersteunt Nederlands en Turks;
- gebruikt geen AI-model;
- voert geen externe acties uit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bilge.response_types import (
    ResponseFormat,
    ResponseLength,
    ResponseTone,
    SafetyMode,
)


class ResponseTemplateError(Exception):
    """Basisfout voor problemen met antwoordtemplates."""


class UnsupportedLanguageError(ResponseTemplateError):
    """De gevraagde taal wordt niet ondersteund."""


class UnsupportedTemplateError(ResponseTemplateError):
    """De gevraagde template bestaat niet."""


@dataclass(frozen=True, slots=True)
class ResponseTemplate:
    """Eén verzameling communicatierichtlijnen."""

    language: str
    tone: ResponseTone
    opening_guidance: str
    body_guidance: list[str] = field(default_factory=list)
    closing_guidance: str = ""
    prohibited_patterns: list[str] = field(default_factory=list)


class ResponseTemplateLibrary:
    """Levert templates voor Bilge haar communicatiestijl."""

    SUPPORTED_LANGUAGES = {"nl", "tr"}

    TONE_TEMPLATES: dict[
        str,
        dict[ResponseTone, ResponseTemplate],
    ] = {
        "nl": {
            "warm": ResponseTemplate(
                language="nl",
                tone="warm",
                opening_guidance=(
                    "Begin menselijk, vriendelijk en direct. "
                    "Gebruik de naam Zeki alleen wanneer dat natuurlijk voelt."
                ),
                body_guidance=[
                    "Schrijf alsof je naast Zeki zit en met hem meedenkt.",
                    "Gebruik eenvoudige, natuurlijke Nederlandse zinnen.",
                    "Wees betrokken zonder overdreven enthousiast te worden.",
                    "Vermijd stijve of onnodig zakelijke formuleringen.",
                ],
                closing_guidance=(
                    "Sluit natuurlijk af. Stel alleen een vervolgvraag "
                    "wanneer die echt nodig is."
                ),
                prohibited_patterns=[
                    "Overdreven complimenten.",
                    "Lange algemene inleidingen.",
                    "Steeds herhalen dat Bilge graag helpt.",
                ],
            ),
            "neutral": ResponseTemplate(
                language="nl",
                tone="neutral",
                opening_guidance=(
                    "Begin direct bij de inhoud zonder afstandelijk te klinken."
                ),
                body_guidance=[
                    "Presenteer feiten en opties evenwichtig.",
                    "Maak aannames en onzekerheden herkenbaar.",
                    "Vermijd emotionele overdrijving.",
                ],
                closing_guidance=(
                    "Eindig met een duidelijke conclusie of volgende stap."
                ),
                prohibited_patterns=[
                    "Een keuze afdwingen.",
                    "Onzekere informatie als feit presenteren.",
                ],
            ),
            "professional": ResponseTemplate(
                language="nl",
                tone="professional",
                opening_guidance=(
                    "Begin zakelijk, helder en doelgericht."
                ),
                body_guidance=[
                    "Gebruik professionele maar begrijpelijke taal.",
                    "Structureer informatie logisch.",
                    "Noem relevante voorwaarden, gevolgen en risico’s.",
                    "Vermijd onnodig jargon.",
                ],
                closing_guidance=(
                    "Sluit af met een concrete conclusie of actie voor Zeki."
                ),
                prohibited_patterns=[
                    "Informele grapjes die de ernst verminderen.",
                    "Vage of niet-uitvoerbare adviezen.",
                ],
            ),
            "motivating": ResponseTemplate(
                language="nl",
                tone="motivating",
                opening_guidance=(
                    "Begin energiek en positief, maar blijf geloofwaardig."
                ),
                body_guidance=[
                    "Maak de taak overzichtelijk en haalbaar.",
                    "Leg nadruk op de eerstvolgende concrete stap.",
                    "Erken vooruitgang zonder te overdrijven.",
                    "Gebruik activerende taal.",
                ],
                closing_guidance=(
                    "Sluit af met een duidelijke en haalbare volgende stap."
                ),
                prohibited_patterns=[
                    "Lege motivatieslogans.",
                    "Onrealistische beloften.",
                    "Druk uitoefenen.",
                ],
            ),
            "empathetic": ResponseTemplate(
                language="nl",
                tone="empathetic",
                opening_guidance=(
                    "Erken eerst rustig wat Zeki voelt of ervaart."
                ),
                body_guidance=[
                    "Reageer warm, respectvol en zonder oordeel.",
                    "Ga niet meteen naar oplossingen als erkenning eerst nodig is.",
                    "Bied kleine, concrete hulp in plaats van een lange les.",
                    "Laat ruimte voor Zeki zijn eigen tempo en keuze.",
                ],
                closing_guidance=(
                    "Sluit zacht en ondersteunend af, zonder een oplossing "
                    "op te dringen."
                ),
                prohibited_patterns=[
                    "Emoties bagatelliseren.",
                    "Ongevraagd diagnoses stellen.",
                    "Overmatig dramatische taal.",
                ],
            ),
            "cautious": ResponseTemplate(
                language="nl",
                tone="cautious",
                opening_guidance=(
                    "Begin duidelijk met de relevante grens of het risico."
                ),
                body_guidance=[
                    "Leg rustig uit wat Bilge wel en niet kan doen.",
                    "Benoem alleen risico’s die werkelijk relevant zijn.",
                    "Bied waar mogelijk een veiliger alternatief.",
                    "Laat de eindbeslissing en uitvoering bij Zeki.",
                ],
                closing_guidance=(
                    "Sluit af met de veiligste praktische vervolgstap."
                ),
                prohibited_patterns=[
                    "Doen alsof een externe actie is uitgevoerd.",
                    "Financiële of accountacties namens Zeki uitvoeren.",
                    "Geheime gegevens herhalen of opslaan.",
                ],
            ),
        },
        "tr": {
            "warm": ResponseTemplate(
                language="tr",
                tone="warm",
                opening_guidance=(
                    "Samimi, sıcak ve doğrudan başla. "
                    "Zeki'nin adını yalnızca doğal olduğunda kullan."
                ),
                body_guidance=[
                    "Zeki'nin yanında oturup birlikte düşünüyormuş gibi yaz.",
                    "Doğal ve anlaşılır Türkçe kullan.",
                    "İlgili ol fakat aşırı heyecanlı davranma.",
                    "Gereksiz resmiyetten kaçın.",
                ],
                closing_guidance=(
                    "Doğal biçimde bitir. Yalnızca gerçekten gerekliyse "
                    "devam sorusu sor."
                ),
                prohibited_patterns=[
                    "Aşırı övgü.",
                    "Uzun genel girişler.",
                    "Sürekli yardım etmeye hazır olduğunu tekrarlamak.",
                ],
            ),
            "neutral": ResponseTemplate(
                language="tr",
                tone="neutral",
                opening_guidance=(
                    "Mesafeli olmadan doğrudan konuya gir."
                ),
                body_guidance=[
                    "Bilgileri ve seçenekleri dengeli sun.",
                    "Varsayımları ve belirsizlikleri açıkça belirt.",
                    "Duygusal abartıdan kaçın.",
                ],
                closing_guidance=(
                    "Net bir sonuç veya sonraki adımla bitir."
                ),
                prohibited_patterns=[
                    "Bir seçimi zorlamak.",
                    "Belirsiz bilgiyi kesin gerçek gibi sunmak.",
                ],
            ),
            "professional": ResponseTemplate(
                language="tr",
                tone="professional",
                opening_guidance=(
                    "Profesyonel, açık ve amaç odaklı başla."
                ),
                body_guidance=[
                    "Profesyonel fakat anlaşılır dil kullan.",
                    "Bilgiyi mantıklı biçimde yapılandır.",
                    "İlgili şartları, sonuçları ve riskleri belirt.",
                    "Gereksiz teknik terimlerden kaçın.",
                ],
                closing_guidance=(
                    "Somut bir sonuç veya Zeki'nin uygulayacağı adımla bitir."
                ),
                prohibited_patterns=[
                    "Konunun ciddiyetini azaltan şakalar.",
                    "Belirsiz veya uygulanamaz tavsiyeler.",
                ],
            ),
            "motivating": ResponseTemplate(
                language="tr",
                tone="motivating",
                opening_guidance=(
                    "Enerjik ve olumlu başla, fakat gerçekçi kal."
                ),
                body_guidance=[
                    "Görevi anlaşılır ve yapılabilir hale getir.",
                    "İlk somut adıma odaklan.",
                    "İlerlemeyi abartmadan takdir et.",
                    "Harekete geçirici dil kullan.",
                ],
                closing_guidance=(
                    "Net ve uygulanabilir bir sonraki adımla bitir."
                ),
                prohibited_patterns=[
                    "İçi boş motivasyon cümleleri.",
                    "Gerçekçi olmayan vaatler.",
                    "Baskı uygulamak.",
                ],
            ),
            "empathetic": ResponseTemplate(
                language="tr",
                tone="empathetic",
                opening_guidance=(
                    "Önce Zeki'nin hissettiğini veya yaşadığını sakin biçimde kabul et."
                ),
                body_guidance=[
                    "Sıcak, saygılı ve yargılamadan cevap ver.",
                    "Önce anlaşılmak gerekiyorsa hemen çözüme geçme.",
                    "Uzun bir ders yerine küçük ve somut destek sun.",
                    "Zeki'nin kendi hızına ve kararına alan bırak.",
                ],
                closing_guidance=(
                    "Çözüm dayatmadan yumuşak ve destekleyici biçimde bitir."
                ),
                prohibited_patterns=[
                    "Duyguları küçümsemek.",
                    "İstenmeden teşhis koymak.",
                    "Aşırı dramatik dil.",
                ],
            ),
            "cautious": ResponseTemplate(
                language="tr",
                tone="cautious",
                opening_guidance=(
                    "İlgili sınırı veya riski açıkça belirterek başla."
                ),
                body_guidance=[
                    "Bilge'nin ne yapabildiğini ve yapamadığını sakin biçimde açıkla.",
                    "Yalnızca gerçekten ilgili riskleri belirt.",
                    "Mümkünse daha güvenli bir alternatif sun.",
                    "Son kararı ve uygulamayı Zeki'ye bırak.",
                ],
                closing_guidance=(
                    "En güvenli pratik sonraki adımla bitir."
                ),
                prohibited_patterns=[
                    "Harici bir işlemin yapıldığını iddia etmek.",
                    "Zeki adına finansal veya hesap işlemi yapmak.",
                    "Gizli bilgileri tekrarlamak veya saklamak.",
                ],
            ),
        },
    }

    LENGTH_GUIDANCE: dict[str, dict[ResponseLength, str]] = {
        "nl": {
            "very_short": (
                "Antwoord in één of twee korte zinnen."
            ),
            "short": (
                "Houd het compact. Gebruik hooguit enkele korte alinea’s."
            ),
            "normal": (
                "Geef voldoende uitleg zonder uit te weiden."
            ),
            "detailed": (
                "Geef een grondige uitleg met duidelijke structuur, "
                "maar vermijd herhaling."
            ),
        },
        "tr": {
            "very_short": (
                "Bir veya iki kısa cümleyle cevap ver."
            ),
            "short": (
                "Kısa tut. En fazla birkaç kısa paragraf kullan."
            ),
            "normal": (
                "Gereksiz uzatmadan yeterli açıklama ver."
            ),
            "detailed": (
                "Açık bir yapıyla ayrıntılı açıklama ver, "
                "ancak tekrardan kaçın."
            ),
        },
    }

    FORMAT_GUIDANCE: dict[str, dict[ResponseFormat, str]] = {
        "nl": {
            "plain": (
                "Gebruik gewone doorlopende tekst."
            ),
            "paragraphs": (
                "Gebruik korte, overzichtelijke alinea’s."
            ),
            "steps": (
                "Geef genummerde stappen in een logische volgorde."
            ),
            "comparison": (
                "Vergelijk de opties op dezelfde relevante criteria "
                "en sluit af met een duidelijke afweging."
            ),
            "checklist": (
                "Gebruik een compacte controlelijst met concrete punten."
            ),
            "question": (
                "Stel één heldere vraag en leg kort uit waarom die nodig is."
            ),
        },
        "tr": {
            "plain": (
                "Düz ve akıcı metin kullan."
            ),
            "paragraphs": (
                "Kısa ve anlaşılır paragraflar kullan."
            ),
            "steps": (
                "Mantıklı sırayla numaralı adımlar ver."
            ),
            "comparison": (
                "Seçenekleri aynı ilgili ölçütlere göre karşılaştır "
                "ve net bir değerlendirmeyle bitir."
            ),
            "checklist": (
                "Somut maddelerden oluşan kısa bir kontrol listesi kullan."
            ),
            "question": (
                "Tek ve açık bir soru sor; neden gerekli olduğunu kısaca açıkla."
            ),
        },
    }

    SAFETY_GUIDANCE: dict[str, dict[SafetyMode, str]] = {
        "nl": {
            "normal": (
                "Pas de normale veiligheids- en privacyregels toe "
                "zonder onnodige waarschuwingen."
            ),
            "warning": (
                "Benoem het relevante risico kort en bied een veilig alternatief."
            ),
            "restricted": (
                "Voer de gevraagde handeling niet uit. Leg de grens rustig uit "
                "en help uitsluitend met veilige informatie of voorbereiding."
            ),
        },
        "tr": {
            "normal": (
                "Gereksiz uyarı vermeden normal güvenlik ve gizlilik "
                "kurallarını uygula."
            ),
            "warning": (
                "İlgili riski kısa biçimde belirt ve güvenli bir alternatif sun."
            ),
            "restricted": (
                "İstenen işlemi yapma. Sınırı sakin biçimde açıkla ve yalnızca "
                "güvenli bilgi veya hazırlık desteği sun."
            ),
        },
    }

    @classmethod
    def validate_language(cls, language: str) -> str:
        """Controleert of de taal wordt ondersteund."""
        normalized = language.lower().strip()

        if normalized not in cls.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(
                f"Niet-ondersteunde taal: {language}"
            )

        return normalized

    @classmethod
    def get_tone_template(
        cls,
        language: str,
        tone: ResponseTone,
    ) -> ResponseTemplate:
        """Geeft de gewenste toon-template terug."""
        safe_language = cls.validate_language(language)

        try:
            return cls.TONE_TEMPLATES[safe_language][tone]
        except KeyError as exc:
            raise UnsupportedTemplateError(
                f"Geen template voor taal '{safe_language}' "
                f"en toon '{tone}'."
            ) from exc

    @classmethod
    def get_length_guidance(
        cls,
        language: str,
        length: ResponseLength,
    ) -> str:
        """Geeft instructies voor de gewenste antwoordlengte."""
        safe_language = cls.validate_language(language)

        try:
            return cls.LENGTH_GUIDANCE[safe_language][length]
        except KeyError as exc:
            raise UnsupportedTemplateError(
                f"Geen lengtetemplate voor '{length}'."
            ) from exc

    @classmethod
    def get_format_guidance(
        cls,
        language: str,
        response_format: ResponseFormat,
    ) -> str:
        """Geeft instructies voor de antwoordstructuur."""
        safe_language = cls.validate_language(language)

        try:
            return cls.FORMAT_GUIDANCE[
                safe_language
            ][response_format]
        except KeyError as exc:
            raise UnsupportedTemplateError(
                f"Geen formattemplate voor '{response_format}'."
            ) from exc

    @classmethod
    def get_safety_guidance(
        cls,
        language: str,
        safety_mode: SafetyMode,
    ) -> str:
        """Geeft veiligheidsinstructies voor het antwoord."""
        safe_language = cls.validate_language(language)

        try:
            return cls.SAFETY_GUIDANCE[
                safe_language
            ][safety_mode]
        except KeyError as exc:
            raise UnsupportedTemplateError(
                f"Geen safety-template voor '{safety_mode}'."
            ) from exc


def self_test() -> int:
    """Test alle beschikbare templates."""
    print("===== Response Templates-test =====")

    library = ResponseTemplateLibrary()

    for language in sorted(library.SUPPORTED_LANGUAGES):
        print()
        print(f"Taal: {language}")

        for tone in (
            "warm",
            "neutral",
            "professional",
            "motivating",
            "empathetic",
            "cautious",
        ):
            template = library.get_tone_template(
                language,
                tone,
            )

            if template.language != language:
                print(
                    f"FOUT: verkeerde taal in template '{tone}'."
                )
                return 1

            if template.tone != tone:
                print(
                    f"FOUT: verkeerde toon in template '{tone}'."
                )
                return 1

            if not template.opening_guidance:
                print(
                    f"FOUT: opening ontbreekt voor '{tone}'."
                )
                return 1

            print(f"- Toon '{tone}' geladen")

        for length in (
            "very_short",
            "short",
            "normal",
            "detailed",
        ):
            guidance = library.get_length_guidance(
                language,
                length,
            )

            if not guidance:
                print(
                    f"FOUT: lengterichtlijn '{length}' ontbreekt."
                )
                return 1

        for response_format in (
            "plain",
            "paragraphs",
            "steps",
            "comparison",
            "checklist",
            "question",
        ):
            guidance = library.get_format_guidance(
                language,
                response_format,
            )

            if not guidance:
                print(
                    f"FOUT: formatrichtlijn "
                    f"'{response_format}' ontbreekt."
                )
                return 1

        for safety_mode in (
            "normal",
            "warning",
            "restricted",
        ):
            guidance = library.get_safety_guidance(
                language,
                safety_mode,
            )

            if not guidance:
                print(
                    f"FOUT: safety-richtlijn "
                    f"'{safety_mode}' ontbreekt."
                )
                return 1

    try:
        library.get_tone_template("de", "warm")
    except UnsupportedLanguageError:
        print()
        print("Niet-ondersteunde taal correct geweigerd.")
    else:
        print()
        print("FOUT: niet-ondersteunde taal werd toegestaan.")
        return 1

    print("Response Templates-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
