# Інженерний пріоритет ПЛЕЙНБУД

Базове дерево — `263096d6be84f48cff1eb5fbd338f543206a93cd` (GitHub `main` на 25.11.2026). Кандидат канону `92b364f1fd1347bc1fccb1efd1653305af4223b1` додає два документи й два тести поверх тієї самої реалізації вебсайту. Об’єкт оптимізації — мобільний шлях від першого кадру до каталогу, кошторису й підтвердження прийняття заявки.

## Вимір і критерій рішення

1. **Достовірність лабораторії.** Існуючий `tools/perf_probe.py` у базовій версії придушує помилку реєстрації `layout-shift`. Відсутність джерела подій дає ті самі `[]` і CLS 0, що й справжня відсутність зсувів. Негативний контроль має зірвати гейт при відмові реєстрації. Позитивний контроль — успішна реєстрація без подій дає 0. Залишаємо дві теми, холодні Chrome-контексти, поточні пороги та сирі результати. Синтетичний LCP/CLS описує лише зафіксований профіль. [1, 2]
2. **Критичний шлях героя.** Спочатку зафіксувати фактичного LCP-кандидата й, де застосовно, TTFB, затримку старту ресурсу, завантаження й затримку рендерингу. Історичний слід заголовка є в `docs/DESIGN.md`, але поточні затримки появи слів і запуск медіа після load/idle вимагають окремих A/B. Чергувати базу й один варіант у холодних контекстах, одна тема/viewport/тротлінг на серію, показати сирі значення. Перша гіпотеза — видимий H1 у першому кадрі зменшує render delay зі стабільним макетом і CTA. Відхилити, якщо ранній H1 не зменшує релевантну підфазу відтворювано. Друга гіпотеза — дешевша портретна рендиція зменшує transfer і декодування під фіксованим сценарієм, з прийнятним візуальним порівнянням. Окремо записати байти до першого екрана, після 5 с і після скролу. Локальний розмір відеофайлу та метрика SSIM/VMAF не замінюють ці виміри. [3, 4, 5]
3. **Мобільні брами.** Playwright уже входить у CI. Розширювати наявні сценарії там, де зміна ризикує поведінкою: відмова autoplay → видимий постер і активний CTA, відмова мережі → повтор тієї самої заявки, клавіатура → доступний кошторис. Chromium, Firefox і Playwright WebKit дають перевірку рушіїв. Фізичні iPhone Safari (у т. ч. Low Power Mode) та Android Chrome потрібні для декодування, роботи після background/foreground і dropped frames. Один requestAnimationFrame для всього сайту — гіпотеза, яку приймаємо після профілювання кадрової роботи на 60/120 Гц і parity reduced motion, pause та visibility. [6, 7, 8]
4. **Польовий доказ.** Пошук достатнього покриття в CrUX перед додаванням телеметрії. Якщо покриття нема, після дозволеного пілота — власний агрегат через закріплену self-hosted збірку `web-vitals`, без полів форми, повних URL чи стабільних ідентифікаторів. Рахувати p75 із розміром вибірки окремо для кожної метрики, релізу й класу пристрою. Орієнтири Google: LCP ≤ 2500 мс, INP ≤ 200 мс, CLS ≤ 0,1. Відсутність INP, зокрема без взаємодії, залишається невідомою. [1, 9]
5. **Доставка і відкат.** Використати чинні exact-SHA CI та процедуру резервування. Для дозволеного стенда розгортати той самий перевірений артефакт і звіряти його SHA-256; відрепетирувати повернення попереднього артефакту, перевіривши health і тестовий прийом заявки з його receipt. До пілота зафіксувати межі та SLI прийняття/доставки окремо, також граничний час виявлення й відкату. Контрольну групу додавати після демонстрації достатнього трафіку для виявлення матеріальної деградації. [10, 11]

Зберігати один стек. Наявні node/pytest/Playwright, власний CDP probe, CI та SHA-256 покривають перший експеримент. Lighthouse і Chrome DevTools використовуються для діагностики розбіжностей. Міграцію на фреймворк або бандлер розглядати з конкретним виграшем і доказом сумісності трьох офлайн-артефактів `tools/inline.py`, теми до першого кадру та контракту заявки.

## Першоджерела

1. Philip Walton, Google Chrome. *Web Vitals*, 2020, оновлено 2024. Польові пороги та межі лабораторії. [Google](https://web.dev/articles/vitals) · [GoogleChrome/web-vitals](https://github.com/GoogleChrome/web-vitals).
2. Google Chrome. *Lighthouse CI*. Лабораторні повтори й асерти на бюджет. [GoogleChrome/lighthouse-ci](https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md).
3. Google Chrome. *Optimize Largest Contentful Paint*. Атрибуція та підфази LCP. [Google](https://web.dev/articles/optimize-lcp).
4. Ravi Netravali, Ameesh Goyal, James Mickens, Hari Balakrishnan, MIT CSAIL і Harvard. *Polaris: Faster Page Loads Using Fine-grained Dependency Tracking*. USENIX NSDI, 2016. Опублікований результат їхнього експерименту не переноситься чисельно на ПЛЕЙНБУД. [USENIX](https://www.usenix.org/conference/nsdi16/technical-sessions/presentation/netravali).
5. Google Chrome. *Video performance*. Вибір моменту завантаження відео й постера. Netflix. *VMAF*. Додатковий інструмент порівняння еквівалентного контенту. [Google](https://web.dev/learn/performance/video-performance) · [Netflix/vmaf](https://github.com/Netflix/vmaf).
6. Microsoft. *Playwright, Browsers*. Матриця рушіїв і межі WebKit-перевірки. [Microsoft](https://playwright.dev/docs/browsers#webkit) · [microsoft/playwright](https://github.com/microsoft/playwright).
7. Jer Noble, Apple WebKit. *New video Policies for iOS*, 2016. Політика autoplay, inline playback і результат `play()`. [WebKit](https://webkit.org/blog/6784/new-video-policies-for-ios/).
8. Google Chrome. *How to create high-performance CSS animations*. Профілювання layout, paint і compositing. [Google](https://web.dev/articles/animations-guide).
9. Google Chrome. *Chrome UX Report methodology*. Популяція Chrome і мінімальні умови включення даних. [Google](https://developer.chrome.com/docs/crux/methodology).
10. Google SRE. *The Site Reliability Workbook*, 2018. SLI/SLO, паралельний контроль і межі canary. [Implementing SLOs](https://sre.google/workbook/implementing-slos/) · [Canarying Releases](https://sre.google/workbook/canarying-releases/).
11. Clare Liguori, AWS. *Automating safe, hands-off deployments*, 2020. Стадії, аларми й автоматичний відкат. [AWS Builders’ Library](https://aws.amazon.com/builders-library/automating-safe-hands-off-deployments/).

## Зафіксована база

`92b364f1fd1347bc1fccb1efd1653305af4223b1`, Chromium headless, localhost, 390×844/DPR 2, CPU 4×, 150 мс, 200 000 Б/с, 3 холодні запуски на тему. Вихід базового probe 0.

- `sky`: LCP 1964 / 1368 / 1348 мс, CLS 0,00844 / 0,00765 / 0,00617.
- `precision`: LCP 1448 / 1528 / 1568 мс, CLS 0,00184 у кожному запуску.
- Сума `ResourceTiming.transferSize` до завершення вікна виміру — 1 146 995 Б у кожному запуску, без навігації, повного скролу й неповних передач. INP та досвід реальних пристроїв відкриті.

Формат лабораторного артефакту 3 вимагає успішної реєстрації LCP/CLS у кожному зразку. Поточний офлайн-гейт відхиляє формат 2. Історичні артефакти відтворюються верифікатором їхньої ревізії з історичними межами методу.
