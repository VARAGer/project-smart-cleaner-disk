from copy import deepcopy


DEMO_BUNDLES = [
    {
        "bundle_id": "review-30d",
        "name": "Review Bundle",
        "description": "Исключённые файлы старше 30 дней",
        "review": True,
        "files": [
            {
                "filename": "draft_notes_2023.docx",
                "size_bytes": 2_516_582,
                "category": "Документы",
                "confidence": 0.92,
                "reason": "Файл был исключён ранее и ждёт повторного просмотра.",
            },
            {
                "filename": "vacation_2019.mov",
                "size_bytes": 1_932_735_283,
                "category": "Видео",
                "confidence": 0.88,
                "reason": "Крупный медиaфайл, давно не использовался.",
            },
            {
                "filename": "setup_old.msi",
                "size_bytes": 47_815_065,
                "category": "Приложения",
                "confidence": 0.91,
                "reason": "Старый установщик без активности.",
            },
        ],
    },
    {
        "bundle_id": "march-2024",
        "name": "Март 2024",
        "description": "Файлы старше 12 месяцев",
        "review": False,
        "files": [
            {
                "filename": "old_report_2021.docx",
                "size_bytes": 2_516_582,
                "category": "Документы",
                "confidence": 0.92,
                "reason": "Старый документ, давно не открывался.",
            },
            {
                "filename": "vacation_photo_2019.jpg",
                "size_bytes": 4_299_161,
                "category": "Изображения",
                "confidence": 0.89,
                "reason": "Файл лежит вне активных рабочих каталогов.",
            },
            {
                "filename": "installer_old.exe",
                "size_bytes": 82_313_420,
                "category": "Приложения",
                "confidence": 0.94,
                "reason": "Старый установщик, давно не запускался.",
            },
            {
                "filename": "movie_2018.mp4",
                "size_bytes": 1_932_735_283,
                "category": "Видео",
                "confidence": 0.90,
                "reason": "Большой медиaфайл с низкой активностью.",
            },
            {
                "filename": "project_notes_current.txt",
                "size_bytes": 32_768,
                "category": "Документы",
                "confidence": 0.38,
                "reason": "Низкая уверенность, файл может быть актуальным.",
            },
        ],
    },
    {
        "bundle_id": "february-2024",
        "name": "Февраль 2024",
        "description": "Файлы старше 13 месяцев",
        "review": False,
        "files": [
            {
                "filename": "legacy_invoice.xlsx",
                "size_bytes": 1_258_291,
                "category": "Документы",
                "confidence": 0.94,
                "reason": "Старый архивный счёт без новых правок.",
            },
            {
                "filename": "music_album_2017.mp3",
                "size_bytes": 117_440_512,
                "category": "Аудио",
                "confidence": 0.85,
                "reason": "Аудиофайл из старой медиатеки.",
            },
            {
                "filename": "unused_iso.iso",
                "size_bytes": 3_328_598_016,
                "category": "Другое",
                "confidence": 0.87,
                "reason": "Крупный образ диска без недавнего доступа.",
            },
        ],
    },
]


def get_demo_bundles() -> list[dict]:
    return deepcopy(DEMO_BUNDLES)