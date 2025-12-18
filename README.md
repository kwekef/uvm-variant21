# Описание
edu-vm — учебная виртуальная машина (УВМ), реализующая ассемблер и интерпретатор в соответствии со спецификацией варианта №21. Проект содержит веб-интерфейс, графический GUI и инструменты автоматического тестирования.

Ассемблерный язык УВМ описывается в формате CSV, дамп памяти формируется в формате XML.

Ключевые свойства:
* Веб-интерфейс (Flask) для демонстрации работы УВМ в браузере
* Графический интерфейс (PySide6)
* Ассемблер и интерпретатор учебной виртуальной машины (вариант 21)
* Поддержка бинарной операции POW
* Автоматическое тестирование (encoding и execution)
* Makefile для основных рабочих сценариев

Формат программы

Каждая строка CSV-файла соответствует одной инструкции. Комментарии начинаются с символа #.

Пример:

LOAD_CONST,0,300
READ_MEM,0,2,0
WRITE_MEM,2,400

Инструкции (вариант 21)

LOAD_CONST B C
Загрузка константы C в регистр B.

READ_MEM B C D
Чтение значения MEM[REG[B] + D] в регистр C.

WRITE_MEM B C
Запись значения регистра B в память по адресу C.

POW B C D E
REG[C] = pow(MEM[REG[E] + D], MEM[REG[B]])

# Описание модулей
main.py — единая точка входа (режимы gui, web, tests)
src/assembler.py — ассемблер CSV → IR → байт-код
src/interpreter.py — интерпретатор учебной виртуальной машины
src/web/app.py — Flask-точка входа для веб-версии
templates/index.html и static/style.css — фронтенд веб-интерфейса
src/gui/main_gui.py — графический интерфейс (PySide6)
src/gui_backend.py — мост между GUI/Web и ядром
src/utils.py — вспомогательные функции
tools/run_tests.py — автоматический запуск тестов
tests/ — CSV-файлы тестов

# Настройки и переменные Makefile / окружения

Makefile содержит ключевые переменные:
POETRY — команда poetry
PY — запуск Python через poetry
SCRIPT — главный скрипт main.py
HOST — адрес (по умолчанию 0.0.0.0)
PORT — порт (по умолчанию 5000)

Основные команды Makefile:
install — установка зависимостей
run-web — запуск веб-версии
run-gui — запуск GUI
run-tests — запуск автоматических тестов
export-requirements — экспорт requirements.txt
clean — очистка временных файлов

# Сборка проекта

Установка
git clone https://github.com/eternal-git-dev/uvm-variant21
cd edu-vm
make install
или
poetry install

Запуск веб-версии
make run-web

Запуск GUI
make run-gui

Запуск тестов
make run-tests

# Примеры использования

Веб-интерфейс — главная страница
<img width="1790" height="1122" alt="image" src="https://github.com/user-attachments/assets/d4fdc118-5eff-4cb9-b007-b9cd7b3fd4d3" />

GUI — окно исполнения
<img width="1249" height="911" alt="image" src="https://github.com/user-attachments/assets/410c490d-bd98-4a92-a53f-595a22e03ba1" />
