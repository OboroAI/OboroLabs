# Структура кода и тесты

[OboroLabs](../../README.ru.md) · [English](../en/development.md)

Клиент использует стандартную библиотеку Python 3.11 или новее. Установленная команда `oborolabs` и `python3 -m imagebench` запускают один и тот же CLI.

- [CLI](../../imagebench/cli.py) обрабатывает команды. [Планирование](../../imagebench/plan.py) проверяет конфигурацию и собирает задания, а [подстановка параметров](../../imagebench/workflow.py) заполняет граф API.
- [Запуск](../../imagebench/runner.py) управляет прогревом и возобновлением. [Клиент ComfyUI](../../imagebench/comfy.py) замеряет HTTP-запросы, а [хранилище](../../imagebench/storage.py) отвечает за блокировку, проверку и запись файлов.
- [Отчёт](../../imagebench/report.py) экспортирует проверенные записи. [Замеры](../../imagebench/timing.py) рассчитывают статистику времени, а [качество](../../imagebench/quality.py) отвечает за импорт оценок и сравнение общих случаев.
- [Адаптеры оценщиков](../../imagebench/evaluators) запускают Tesseract и HPS и обмениваются изображениями и оценками с CompBench++.
- В [types](../../imagebench/types) лежат общие схемы. В [constants](../../imagebench/constants) хранятся ограничения, значения по умолчанию и заголовки CSV.

## Запуск тестов

```bash
python3 -m unittest discover -s tests -v
```

Тесты покрывают валидацию плана и графа, целостность файлов и блокировку записи, расчёт времени, протоколы оценки и сценарии командной строки. Для проверок используются тестовые PNG, локальный HTTP-мок ComfyUI и заранее заданные ответы оценщиков. Серверные маршруты описаны в [справочнике API ComfyUI](https://docs.comfy.org/development/comfyui-server/comms_routes).
