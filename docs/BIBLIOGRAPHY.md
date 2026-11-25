# Бібліографія й методична основа сайту ПЛЕЙНБУД

Редакція 25.11.2026, основа — коміт `b8689b8`. Перелічено лише те, що справді вжито в репозиторії, із місцем ужитку.
Документ не є сертифікатом відповідності: відповідність доводять тести й акти, названі в кожному рядку (`docs/CANON.md`).

## Як читати

- **Де вжито** — файл або ціль `make`, які можна відкрити й запустити.
- **Статус запису:**
  - `✔` — автори, назва, видання й рік звірено пошуком 25.11.2026;
  - `▲` — джерело підтверджено, але зв'язок із кодом тримається на вторинному посиланні;
  - `◐` — запис наведено з пам'яті виконавця, пошуком не звірено.
- **Числа звірено** — значення з джерела порівняно з кодом і закріплено тестом `tests/test_bibliography_values.py`.
- Статус стосується запису про джерело. Чи код правильно його реалізує — перевіряють тести.

## 1. Доступність

| Джерело | Де вжито | Статус |
|---|---|---|
| W3C. *Web Content Accessibility Guidelines (WCAG) 2.2*. W3C Recommendation, 5 жовтня 2023; перевидано 12 грудня 2024. https://www.w3.org/TR/WCAG22/ | Поріг AA: контраст ≥ 4,5:1 (великий текст ≥ 3:1), фокус, рух. `tests/test_site.py`, `tests/test_steel_a11y.py`, `tests/test_premium_visual.py`, `tools/sky.py` | ✔ |
| Deque Systems. *axe-core* — рушій автоматичних перевірок доступності, ліцензія MPL 2.0. https://github.com/dequelabs/axe-core | Браузерні тести: `tests/test_site.py` | ✔ |
| W3C. *Media Queries Level 5* (Working Draft) — `prefers-reduced-motion`. https://www.w3.org/TR/mediaqueries-5/ | Вимкнення руху: `web/css/site.css` | ✔ |

Межа: автоматика не замінює оцінки людиною з екранним читачем — відкритий пункт H1 у `docs/PRODUCTION_HOLD.md`.

## 2. Швидкість

| Джерело | Де вжито | Статус |
|---|---|---|
| Google / web.dev. *How the Core Web Vitals metrics thresholds were defined*, 2020, оновл. 7 травня 2025: LCP ≤ 2,5 с, INP ≤ 200 мс, CLS ≤ 0,1 на 75-му перцентилі. https://web.dev/articles/defining-core-web-vitals-thresholds | Пороги якості в `AGENTS.md`; лабораторні виміри в `docs/DESIGN.md` | ✔ |
| Google. *Lighthouse*. https://github.com/GoogleChrome/lighthouse | Лабораторні виміри 24.11.2026 у `docs/DESIGN.md` | ◐ |

Межа: польових даних немає (пункт F1); після теми «Атмосфера» швидкість не переміряно.

## 3. Безпека й цілісність

| Джерело | Де вжито | Статус |
|---|---|---|
| OWASP. *Application Security Verification Standard 5.0.0*, 30 травня 2025. https://owasp.org/www-project-application-security-verification-standard/ | Матриця вимог: `docs/SECURITY_ASSURANCE_MATRIX.md` | ✔ |
| Krawczyk H., Bellare M., Canetti R. *HMAC: Keyed-Hashing for Message Authentication*. RFC 2104, лютий 1997 (Informational; оновлено RFC 6151). https://www.rfc-editor.org/rfc/rfc2104 | Підпис заявки HMAC-SHA256: `server/app.py` | ✔ |
| NIST. *FIPS 180-4, Secure Hash Standard*, серпень 2015. DOI 10.6028/NIST.FIPS.180-4 | SHA-256 для медіа, актів, походження: `docs/PROVENANCE.md` | ✔ |
| Jena J., Dalal S. *The Idempotency-Key HTTP Header Field*. IETF Internet-Draft `draft-ietf-httpapi-idempotency-key-header-07`, жовтень 2025. Чернетка зі строком дії до 18.04.2026; чинний статус не звірено. | Повтор заявки без дубля: `server/app.py`, `tests/test_leads.py`, `tests/test_lead_reload_idempotency.py` | ✔ |
| W3C. *Content Security Policy Level 3* (Working Draft). https://www.w3.org/TR/CSP3/ | Заголовки: `server/app.py`, `tests/test_themes.py` | ✔ |
| W3C. *Trusted Types* (Working Draft). https://www.w3.org/TR/trusted-types/ | `tests/test_trusted_types.py` | ✔ |
| Google / OpenSSF. *OSV — Open Source Vulnerabilities*, схема опису вразливостей, з 2021. https://osv.dev/ | `.github/workflows/security-assurance.yml` | ✔ |
| PyPA. *pip-audit*. https://pypi.org/project/pip-audit/ | `.github/workflows/security-assurance.yml` | ✔ |
| Ecma International. *ECMA-424, CycloneDX Bill of Materials Specification*, 1-ше вид., червень 2024; 2-ге вид., грудень 2025. | Акт складу залежностей у CI | ✔ |
| OpenSSF. *SLSA — Supply-chain Levels for Software Artifacts*, v1.0, 19 квітня 2023. https://slsa.dev/spec/v1.0/ | Рівень **не заявляється**: у коді `slsa_level: none_claimed` (`tools/meta_evidence_gate.py`) | ✔ |

## 4. Методи перевірки

| Джерело | Де вжито | Статус |
|---|---|---|
| DeMillo R. A., Lipton R. J., Sayward F. G. *Hints on Test Data Selection: Help for the Practicing Programmer*. IEEE Computer 11(4), квітень 1978, с. 34–41. DOI 10.1109/C-M.1978.218136 | Мутаційне тестування: `tools/mutation_run.py`, `config/mutation-catalog.json` | ✔ |
| Claessen K., Hughes J. *QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs*. ICFP 2000, с. 268–279. | Тести властивостей: `tests/quote_engine.test.cjs`, `tests/test_stateful_model.py` | ✔ |
| Kelly T., Weaver R. *The Goal Structuring Notation — A Safety Argument Notation*. DSN 2004 Workshop on Assurance Cases, липень 2004. | Структура доказової справи: `docs/ASSURANCE.md`, `tools/assurance_check.py` | ✔ |
| Reproducible Builds project. https://reproducible-builds.org/ | Байт-ідентичність збірки: `tests/test_reproducibility.py` | ◐ |

## 5. Колір теми: небо й вода (`tools/sky.py`)

| Джерело | Де вжито | Статус |
|---|---|---|
| Strutt J. W. (Lord Rayleigh). *On the light from the sky, its polarization and colour*. Philosophical Magazine 41, 1871, с. 107–120. DOI 10.1080/14786447108640452 | Розсіювання ∝ λ⁻⁴ | ✔ |
| Hansen J. E., Travis L. D. *Light scattering in planetary atmospheres*. Space Science Reviews 16, 1974, с. 527–610. DOI 10.1007/BF00168069. Апроксимація τ = 0,008569·λ⁻⁴·(1 + 0,0113·λ⁻² + 0,00013·λ⁻⁴), λ у мкм, приписується цій праці у зведенні Teillet P. M.; у самій статті формулу не перевірено. | `tau_rayleigh`; коефіцієнти закріплено тестом | ▲ |
| Bodhaine B. A., Wood N. B., Dutton E. G., Slusser J. R. *On Rayleigh Optical Depth Calculations*. J. Atmos. Oceanic Technol. 16(11), 1999, с. 1854–1861. | **Не вжито.** Радить рахувати з перших принципів, а не з апроксимацій; це правильна заміна рядку вище | ✔ |
| Kasten F., Young A. T. *Revised optical air mass tables and approximation formula*. Applied Optics 28(22), 1989, с. 4735–4738. DOI 10.1364/AO.28.004735 | `air_mass`. **Числа звірено** | ✔ |
| Pope R. M., Fry E. S. *Absorption spectrum (380–700 nm) of pure water. II. Integrating cavity measurements*. Applied Optics 36(33), 1997, с. 8710–8723. Дані: https://omlc.org/spectra/water/data/pope97.txt | Таблиця `WATER`, 380–700 нм. **Числа звірено**: 17 значень | ✔ |
| Kou L., Labrie D., Chylek P. *Refractive indices of water and ice in the 0.65- to 2.5-µm spectral range*. Applied Optics 32(19), 1993, с. 3531–3540. DOI 10.1364/AO.32.003531 | Таблиця `WATER`, 720–780 нм; ці чотири значення з таблицею статті **не звірено** | ▲ |
| Wyman C., Sloan P.-P., Shirley P. *Simple Analytic Approximations to the CIE XYZ Color Matching Functions*. Journal of Computer Graphics Techniques 2(2), 2013. | `cmf`. **Числа звірено**: 28 параметрів | ✔ |
| CIE. *CIE 015:2018 Colorimetry, 4th Edition*; ISO/CIE 11664-1:2019, *CIE standard colorimetric observers*. | Стандартний спостерігач 1931 р., 2° | ✔ |
| Ottosson B. *A perceptual color space for image processing* (Oklab), 23 грудня 2020. https://bottosson.github.io/posts/oklab/ | `lin_to_oklab`, `oklab_to_lin`; матриці з текстом публікації не звірено, обернення перевірено тестом | ✔ |
| W3C. *CSS Color Module Level 4* (Candidate Recommendation Draft) — `color(display-p3 …)`. https://www.w3.org/TR/css-color-4/ | Блок `@media (color-gamut:p3)` у `web/css/site.css` | ✔ |

Межа моделі: одноразове розсіювання, без аерозолю й багаторазового розсіювання; поглинання озоном — гаусова апроксимація
**без джерела**; світлість нормовано під читання. Це обчислена стилізація, а не фотометрія.

## 6. Відео

| Джерело | Де вжито | Статус |
|---|---|---|
| Wang Z., Bovik A. C., Sheikh H. R., Simoncelli E. P. *Image Quality Assessment: From Error Visibility to Structural Similarity*. IEEE Trans. Image Processing 13(4), квітень 2004, с. 600–612. DOI 10.1109/TIP.2003.819861 | SSIM у перевірці перекодування: `docs/PROVENANCE.md`, `tools/artifact_video_fit.py` | ✔ |
| Wang X., Xie L., Dong C., Shan Y. *Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic Data*. ICCV Workshops 2021, с. 1905–1914. arXiv:2107.10833 | Збільшення джерел ×2: `tools/sr.py` | ✔ |
| FFmpeg, x264, libvpx-vp9 — документація двопрохідного кодування. https://ffmpeg.org/documentation.html | `tools/media.py` | ◐ |

Не вжито: VMAF — у збірці ffmpeg стенда немає `libvmaf`; у `docs/PROVENANCE.md` прямо написано «не виміряно».

## 7. Карта й маршрути

| Джерело | Де вжито | Статус |
|---|---|---|
| Luxen D., Vetter C. *Real-time routing with OpenStreetMap data*. ACM SIGSPATIAL GIS 2011 (Чикаго, 1–4 листопада 2011), с. 513–516. DOI 10.1145/2093973.2094062 | Відстані дорогою з Полтави (OSRM): `docs/PROVENANCE.md` | ✔ |
| OpenStreetMap contributors. Дані © OpenStreetMap, ліцензія ODbL. https://www.openstreetmap.org/copyright | Те саме | ◐ |
| Runfola D. et al. *geoBoundaries: A global database of political administrative boundaries*. PLoS ONE 15(4), 2020, e0231866. DOI 10.1371/journal.pone.0231866 | Межі областей: `tools/geo_map.py` | ✔ |

## 8. Право

| Джерело | Де вжито | Статус |
|---|---|---|
| Закон України «Про захист персональних даних» № 2297-VI від 1 червня 2010 р., чинний з 1 січня 2011 р. https://zakon.rada.gov.ua/laws/show/2297-17 (чинну редакцію на сайті Ради не відкривав). | Заборона сторонніх трекерів у `AGENTS.md`; відкритий пункт B7 у `docs/PRODUCTION_HOLD.md` | ✔ |

## Підсумок статусів

- 30 записів звірено пошуком (`✔`), 2 підтверджено вторинно (`▲`), 4 (`◐`) наведено з пам'яті.
- Числа з трьох джерел порівняно з кодом і закріплено тестом: вода (17), колірні функції (28), повітряна маса (3 константи).
- Не всі джерела — американські академічні. Це стандарти W3C, IETF, NIST, OWASP, Ecma, CIE/ISO, рецензовані статті
  (Applied Optics, IEEE, JCGT, PLoS ONE, Space Science Reviews, Philosophical Magazine) і документація відкритих інструментів.
- Джерел «для ваги» тут немає: якщо метод не лишив сліду в коді, тесті чи акті — його не вписано.

## Відкрите

1. Апроксимацію релеївської товщі замінити розрахунком за Bodhaine et al. (1999) або звірити формулу з текстом Hansen & Travis (1974).
2. Знайти джерело для перерізу поглинання озону в смузі Шаппюї або прибрати озон із моделі.
3. Звірити чотири значення поглинання води 720–780 нм із таблицею Kou et al. (1993).
4. Звірити матриці Oklab із текстом публікації.
5. Звірити чинний статус чернетки Idempotency-Key і чинну редакцію Закону № 2297-VI.
