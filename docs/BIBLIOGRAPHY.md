# Бібліографія й методична основа сайту ПЛЕЙНБУД

Стан на 25.11.2026, коміт-основа `b8689b8`. Документ перелічує лише те, що справді вжито в цьому репозиторії, і вказує,
де саме. Він не є сертифікатом відповідності жодному стандарту: відповідність доводять тести й акти, названі в кожному рядку.

## Як читати

- **Де вжито** — файл або ціль `make`, які можна відкрити й запустити.
- **Статус запису:**
  - `✔` — бібліографічний запис (автори, назва, видання, рік) звірено пошуком 25.11.2026;
  - `◐` — запис наведено з пам'яті виконавця, з першоджерелом не звірено; перед публічним цитуванням звірити;
  - `▲` — джерело підтверджено лише через вторинне посилання.
- Статус стосується запису про джерело, а не того, чи код правильно його реалізує: це перевіряють тести.

## 1. Доступність

| Джерело | Де вжито | Статус |
|---|---|---|
| W3C. *Web Content Accessibility Guidelines (WCAG) 2.2*. W3C Recommendation, 5 жовтня 2023; перевидано 12 грудня 2024. https://www.w3.org/TR/WCAG22/ | Поріг AA: контраст ≥ 4,5:1 (великий текст ≥ 3:1), фокус, рух. `tests/test_site.py`, `tests/test_steel_a11y.py`, `tests/test_premium_visual.py`, `tools/sky.py` (`audit`) | ✔ |
| Deque Systems. *axe-core* — рушій автоматичних перевірок доступності. https://github.com/dequelabs/axe-core | `tests/vendor/`, браузерні тести | ◐ |
| W3C. *Media Queries Level 5* — `prefers-reduced-motion`. | Вимкнення руху: `web/css/site.css`, `data-quality=static` | ◐ |

Межа: автоматичні перевірки не замінюють оцінки людиною з екранним читачем — відкритий пункт H1 у `docs/PRODUCTION_HOLD.md`.

## 2. Швидкість

| Джерело | Де вжито | Статус |
|---|---|---|
| Google / web.dev. *How the Core Web Vitals metrics thresholds were defined* (2020, оновл. 2025): LCP ≤ 2,5 с, INP ≤ 200 мс, CLS ≤ 0,1 на 75-му перцентилі. https://web.dev/articles/defining-core-web-vitals-thresholds | Пороги §4 `AGENTS.md`; лабораторні виміри в `docs/DESIGN.md` | ✔ |
| Google. *Lighthouse*. | Лабораторні виміри 24.11.2026 у `docs/DESIGN.md` | ◐ |

Межа: польових даних немає (пункт F1); після теми «Атмосфера» швидкість не переміряно.

## 3. Безпека й цілісність

| Джерело | Де вжито | Статус |
|---|---|---|
| OWASP. *Application Security Verification Standard 5.0.0*, 30 травня 2025. https://owasp.org/www-project-application-security-verification-standard/ | Матриця вимог: `docs/SECURITY_ASSURANCE_MATRIX.md` | ✔ |
| Krawczyk H., Bellare M., Canetti R. *HMAC: Keyed-Hashing for Message Authentication*. RFC 2104, 1997. | Підпис заявки `X-PBT-Signature` (HMAC-SHA256): `server/app.py` | ◐ |
| NIST. *FIPS 180-4, Secure Hash Standard*, 2015. | SHA-256 для медіа, актів, походження | ◐ |
| Jena J., Dalal S. *The Idempotency-Key HTTP Header Field*. IETF Internet-Draft `draft-ietf-httpapi-idempotency-key-header-07`, жовтень 2025 (чернетка; чинний статус на datatracker не звірено). | Повтор заявки без дубля: `server/app.py`, `tests/test_lead_reload_idempotency.py` | ✔ |
| W3C. *Content Security Policy Level 3*; W3C. *Trusted Types*. | Заголовки й політика: `server/app.py`, `tests/test_trusted_types.py` | ◐ |
| Google. *OSV — Open Source Vulnerabilities*; PyPA. *pip-audit*. | `.github/workflows/security-assurance.yml` | ◐ |
| OWASP. *CycloneDX* (специфікація SBOM). | Акт складу залежностей у CI | ◐ |
| OpenSSF. *SLSA*. | Рівень **не заявляється**: у коді записано `slsa_level: none_claimed` | ◐ |

## 4. Методи перевірки

| Джерело | Де вжито | Статус |
|---|---|---|
| DeMillo R. A., Lipton R. J., Sayward F. G. *Hints on Test Data Selection: Help for the Practicing Programmer*. IEEE Computer 11(4), 1978, с. 34–41. | Мутаційне тестування: `tools/mutation_run.py`, `config/mutation-catalog.json` | ◐ |
| Claessen K., Hughes J. *QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs*. ICFP 2000. | Тести властивостей ядер: `tests/*.test.cjs`, `tests/test_stateful_model.py` | ◐ |
| Kelly T., Weaver R. *The Goal Structuring Notation — A Safety Argument Notation*. DSN Workshop on Assurance Cases, 2004. | Структура доказової справи: `docs/ASSURANCE.md`, `tools/assurance_check.py` | ◐ |
| Reproducible Builds project. https://reproducible-builds.org/ | Байт-ідентичність збірки в трьох локалях: `tests/test_reproducibility.py` | ◐ |

## 5. Колір теми: небо й вода (`tools/sky.py`)

| Джерело | Де вжито | Статус |
|---|---|---|
| Strutt J. W. (Lord Rayleigh). *On the light from the sky, its polarization and colour*. Philosophical Magazine 41, 1871. | Розсіювання ∝ λ⁻⁴, фазова функція | ◐ |
| Апроксимація оптичної товщі τ = 0,008569·λ⁻⁴·(1 + 0,0113·λ⁻² + 0,00013·λ⁻⁴), λ у мкм; приписується Hansen J. E., Travis L. D. *Light scattering in planetary atmospheres*. Space Science Reviews 16, 1974, у зведенні Teillet P. M. (1990). | `tau_rayleigh` | ▲ |
| Bodhaine B. A., Wood N. B., Dutton E. G., Slusser J. R. *On Rayleigh Optical Depth Calculations*. J. Atmos. Oceanic Technol. 16, 1999. | Не вжито; це сучасніший спосіб, яким варто замінити апроксимацію вище | ▲ |
| Kasten F., Young A. T. *Revised optical air mass tables and approximation formula*. Applied Optics 28(22), 1989, с. 4735–4738. DOI 10.1364/AO.28.004735 | `air_mass` | ✔ |
| Pope R. M., Fry E. S. *Absorption spectrum (380–700 nm) of pure water. II. Integrating cavity measurements*. Applied Optics 36(33), 1997, с. 8710–8723. | Таблиця `WATER` до 700 нм (значення округлено, з таблицею статті не звірено) | ✔ |
| Kou L., Labrie D., Chylek P. *Refractive indices of water and ice in the 0.65- to 2.5-µm spectral range*. Applied Optics 32(19), 1993. | Таблиця `WATER` після 700 нм | ◐ |
| Wyman C., Sloan P.-P., Shirley P. *Simple Analytic Approximations to the CIE XYZ Color Matching Functions*. Journal of Computer Graphics Techniques 2(2), 2013. | `cmf` (коефіцієнти з пам'яті, з текстом статті не звірено) | ✔ |
| CIE. *Colorimetry*, стандартний спостерігач 1931 р., 2°. | Колориметрія | ◐ |
| Ottosson B. *A perceptual color space for image processing* (OKLab), 2020. https://bottosson.github.io/posts/oklab/ | `lin_to_oklab`, `oklab_to_lin` | ◐ |
| W3C. *CSS Color Module Level 4* — `color(display-p3 …)`. | Блок `@media (color-gamut:p3)` | ◐ |

Межа моделі (повторено з `docs/DESIGN.md`): одноразове розсіювання, без аерозолю й багаторазового розсіювання; озон — гаусова
апроксимація без джерела; світлість нормовано під читання. Це обчислена стилізація, а не фотометрія.

## 6. Відео

| Джерело | Де вжито | Статус |
|---|---|---|
| Wang Z., Bovik A. C., Sheikh H. R., Simoncelli E. P. *Image Quality Assessment: From Error Visibility to Structural Similarity*. IEEE Trans. Image Processing 13(4), 2004, с. 600–612. | SSIM у перевірці перекодування: `docs/PROVENANCE.md`, `tools/artifact_video_fit.py` | ◐ |
| Wang X., Xie L., Dong C., Shan Y. *Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic Data*. ICCV Workshops, 2021. | Збільшення джерел ×2: `tools/sr.py` (ваги v0.2.5.0, sha256 закріплено) | ◐ |
| FFmpeg, x264, libvpx-vp9 — документація двопрохідного кодування. | `tools/media.py` | ◐ |

Не вжито: VMAF (Netflix) — у збірці ffmpeg стенда немає `libvmaf`; у документах прямо написано «не виміряно».

## 7. Карта й маршрути

| Джерело | Де вжито | Статус |
|---|---|---|
| Luxen D., Vetter C. *Real-time routing with OpenStreetMap data*. ACM SIGSPATIAL GIS, 2011 (OSRM). | Відстані дорогою з Полтави: `docs/PROVENANCE.md` | ◐ |
| OpenStreetMap contributors. Дані © OpenStreetMap, ліцензія ODbL. | Те саме | ◐ |
| Runfola D. et al. *geoBoundaries: A global database of political administrative boundaries*. PLoS ONE 15(4), 2020, e0231866. | Межі областей: `tools/geo_map.py` | ◐ |

## 8. Право

| Джерело | Де вжито | Статус |
|---|---|---|
| Закон України «Про захист персональних даних» № 2297-VI від 01.06.2010. | Заборона сторонніх трекерів; відкритий пункт B7 (політика конфіденційності) | ◐ |

## Чого в цьому документі немає і чому

- Немає джерел «для ваги». Якщо метод не лишив сліду в коді, тесті чи акті — його тут нема.
- Не всі джерела — американські академічні. Це стандарти W3C, IETF, OWASP, NIST, рецензовані статті (Applied Optics, IEEE TIP,
  JCGT, PLoS ONE) та документація відкритих інструментів. Походження вказано так, як воно є.
- 7 записів звірено пошуком (`✔`), 2 підтверджено вторинно (`▲`), 25 (`◐`) чекають звірки з першоджерелом.
  До публічного використання документа як наукової бібліографії `◐` треба закрити.
