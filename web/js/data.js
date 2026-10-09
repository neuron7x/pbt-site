/* Дані інтерфейсу ПБТ. Джерела: прайс і парк — pbt-spectehnika.com.ua (03.10.2026); реквізити — config/business.json; відео — монтаж із TikTok @poltavabudtehnika (власна зйомка клієнта), tools/media.py. */
window.PBT = {
 "business": {
  "brand": {
   "name": "ПБТ",
   "nameUk": "ПолтаваБудТехніка",
   "alternateName": "PBT Spectehnika"
  },
  "legalName": "ТОВ «ПолтаваБудТехніка»",
  "edrpou": "45383082",
  "city": "Полтава",
  "region": "Полтавська область",
  "address": "36002, м. Полтава, вул. Довженка, 2А",
  "url": "https://pbt-spectehnika.com.ua",
  "logo": "/media/logo/pbt-logo.png",
  "contacts": {
   "phone": "+380978637777",
   "phone2": "+380958637777",
   "email": null,
   "telegram": null,
   "viber": "+380978637777",
   "whatsapp": null,
   "instagram": "https://www.instagram.com/pbtspectehnika",
   "tiktok": "https://www.tiktok.com/@poltavabudtehnika",
   "facebook": "https://www.facebook.com/profile.php?id=61563404525960",
   "youtube": "https://www.youtube.com/channel/UCvSkE5UV_uavxC7fwAU9Ssg"
  },
  "responsiblePerson": null,
  "hours": {
   "mo-fr": "09:00–18:00",
   "sa": "09:00–15:00",
   "su": "вихідний",
   "dispatch": "техніка працює цілодобово"
  },
  "regions": [
   "Полтавська",
   "Черкаська",
   "Дніпропетровська",
   "Харківська",
   "Запорізька",
   "Київська",
   "Кіровоградська",
   "Чернігівська",
   "Житомирська"
  ]
 },
 "priceDate": "2026-10-03",
 "priceSource": "pbt-spectehnika.com.ua",
 "cats": [
  {
   "id": "exc",
   "name": "Екскаватори",
   "lead": "Гусеничні екскаватори 22–44 т: котловани, траншеї, розробка ґрунту."
  },
  {
   "id": "amph",
   "name": "Амфібії й довгі стріли",
   "lead": "Амфібії та довгорукі екскаватори: водойми, мул, очерет, днопоглиблення."
  },
  {
   "id": "bull",
   "name": "Бульдозери",
   "lead": "Планування майданчиків, корчування, переміщення ґрунту."
  },
  {
   "id": "crane",
   "name": "Автокрани",
   "lead": "25–120 т, стріла до 70 м: монтаж, демонтаж, розбирання завалів."
  },
  {
   "id": "load",
   "name": "Навантажувачі",
   "lead": "Фронтальні, телескопічні, екскаватори-навантажувачі."
  },
  {
   "id": "road",
   "name": "Дорожня техніка",
   "lead": "Грейдер, котки, асфальтоукладач, мінітехніка."
  },
  {
   "id": "crush",
   "name": "Дробарки / Мульчери",
   "lead": "Дроблення бетону й каменю, мульчування порослі."
  },
  {
   "id": "trans",
   "name": "Трали / Самоскиди",
   "lead": "Перевезення негабариту до 60 т, самоскиди 30 т."
  }
 ],
 "fleet": [
  {
   "id": "e-1",
   "cat": "exc",
   "name": "Гусеничний екскаватор JCB JS220LC",
   "img": "media/park/e-1.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "22 т"
    },
    {
     "k": "Витрата палива",
     "v": "11 л"
    }
   ],
   "price": 1350,
   "unit": "год"
  },
  {
   "id": "e-2",
   "cat": "exc",
   "name": "Гусеничний екскаватор Volvo EC240",
   "img": "media/park/e-2.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "22 т"
    },
    {
     "k": "Витрата палива",
     "v": "11 л"
    }
   ],
   "price": 1350,
   "unit": "год"
  },
  {
   "id": "e-3",
   "cat": "exc",
   "name": "Гусеничний екскаватор Doosan DX300",
   "img": "media/park/e-3.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "31 т"
    },
    {
     "k": "Витрата палива",
     "v": "19 л"
    }
   ],
   "price": 1500,
   "unit": "год"
  },
  {
   "id": "e-4",
   "cat": "exc",
   "name": "Гусеничний екскаватор Volvo EC480",
   "img": "media/park/e-4.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "44 т"
    },
    {
     "k": "Витрата палива",
     "v": "23 л"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "b-1",
   "cat": "bull",
   "name": "Бульдозер CAT D6R/T",
   "img": "media/park/b-1.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "22 т"
    },
    {
     "k": "Витрата палива",
     "v": "20 л"
    }
   ],
   "price": 1500,
   "unit": "год"
  },
  {
   "id": "b-2",
   "cat": "bull",
   "name": "Бульдозер SEM 816D",
   "img": "media/park/b-2.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "22 т"
    },
    {
     "k": "Витрата палива",
     "v": "18 л"
    }
   ],
   "price": 1500,
   "unit": "год"
  },
  {
   "id": "b-3",
   "cat": "bull",
   "name": "Бульдозер Komatsu D85EX",
   "img": "media/park/b-3.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "30 т"
    },
    {
     "k": "Витрата палива",
     "v": "35 л"
    }
   ],
   "price": 2000,
   "unit": "год"
  },
  {
   "id": "b-4",
   "cat": "bull",
   "name": "Бульдозер-викорчовувач Komatsu D61",
   "img": "media/park/b-4.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "15 т"
    },
    {
     "k": "Витрата палива",
     "v": "15 л"
    }
   ],
   "price": 1600,
   "unit": "год"
  },
  {
   "id": "ak-1",
   "cat": "crane",
   "name": "Автокран 25 т КрАЗ / МАЗ / КамАЗ",
   "img": "media/park/ak-1.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "25 т"
    },
    {
     "k": "Довжина стріли",
     "v": "22 м"
    }
   ],
   "price": 1800,
   "unit": "год"
  },
  {
   "id": "ak-2",
   "cat": "crane",
   "name": "Автокран 55 т Chang Jiang LT1055/1",
   "img": "media/park/ak-2.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "55 т"
    },
    {
     "k": "Довжина стріли",
     "v": "42 м"
    }
   ],
   "price": 3600,
   "unit": "год"
  },
  {
   "id": "ak-3",
   "cat": "crane",
   "name": "Автокран 70 т XCMG QY70KS",
   "img": "media/park/ak-3.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "70 т"
    },
    {
     "k": "Довжина стріли",
     "v": "60 м"
    }
   ],
   "price": 4500,
   "unit": "год"
  },
  {
   "id": "ak-4",
   "cat": "crane",
   "name": "Автокран 120 т Liebherr LTM 1120",
   "img": "media/park/ak-4.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "120 т"
    },
    {
     "k": "Довжина стріли",
     "v": "70 м"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "pe-1",
   "cat": "amph",
   "name": "Плавучий екскаватор-амфібія Volvo EC210BLR",
   "img": "media/park/pe-1.webp",
   "specs": [
    {
     "k": "Довжина стріли",
     "v": "16,5 м"
    },
    {
     "k": "Витрата палива",
     "v": "20 л"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "pe-2",
   "cat": "amph",
   "name": "Плавучий екскаватор-амфібія Hyundai 140-7A Big Float",
   "img": "media/park/pe-2.webp",
   "specs": [
    {
     "k": "Довжина стріли",
     "v": "14 м"
    },
    {
     "k": "Витрата палива",
     "v": "18 л"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "pe-3",
   "cat": "amph",
   "name": "Екскаватор із довгою стрілою Volvo EC210",
   "img": "media/park/pe-3.webp",
   "specs": [
    {
     "k": "Довжина стріли",
     "v": "17 м"
    },
    {
     "k": "Витрата палива",
     "v": "17 л"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "pe-4",
   "cat": "amph",
   "name": "Екскаватор із довгою стрілою Hitachi ZX210LC",
   "img": "media/park/pe-4.webp",
   "specs": [
    {
     "k": "Довжина стріли",
     "v": "16,5 м"
    },
    {
     "k": "Витрата палива",
     "v": "18 л"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "tr-1",
   "cat": "trans",
   "name": "Трал 40 т",
   "img": "media/park/tr-1.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "40 т"
    },
    {
     "k": "Довжина",
     "v": "12 м"
    }
   ],
   "price": 100,
   "unit": "км"
  },
  {
   "id": "tr-2",
   "cat": "trans",
   "name": "Трал 60 т",
   "img": "media/park/tr-2.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "60 т"
    },
    {
     "k": "Довжина",
     "v": "22 м"
    }
   ],
   "price": 140,
   "unit": "км"
  },
  {
   "id": "tr-3",
   "cat": "trans",
   "name": "Напівпричепи",
   "img": "media/park/tr-3.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "40 т"
    }
   ],
   "price": 3,
   "unit": "км"
  },
  {
   "id": "tr-4",
   "cat": "trans",
   "name": "Самоскиди",
   "img": "media/park/tr-4.webp",
   "specs": [
    {
     "k": "Вантажопідйомність",
     "v": "30 т"
    }
   ],
   "price": 80,
   "unit": "км"
  },
  {
   "id": "nav-1",
   "cat": "load",
   "name": "Фронтальний навантажувач Caterpillar 972K",
   "img": "media/park/nav-1.webp",
   "specs": [
    {
     "k": "Витрата палива",
     "v": "12 л"
    }
   ],
   "price": 1400,
   "unit": "год"
  },
  {
   "id": "nav-2",
   "cat": "load",
   "name": "Фронтальний навантажувач Doosan DL400",
   "img": "media/park/nav-2.webp",
   "specs": [
    {
     "k": "Витрата палива",
     "v": "10 л"
    }
   ],
   "price": 1400,
   "unit": "год"
  },
  {
   "id": "nav-3",
   "cat": "load",
   "name": "Екскаватор-навантажувач JCB 3CX",
   "img": "media/park/nav-3.webp",
   "specs": [
    {
     "k": "Витрата палива",
     "v": "7 л"
    }
   ],
   "price": 750,
   "unit": "год"
  },
  {
   "id": "nav-4",
   "cat": "load",
   "name": "Телескопічний навантажувач JCB 540-140",
   "img": "media/park/nav-4.webp",
   "specs": [
    {
     "k": "Обладнання",
     "v": "фронтальний ківш, вила"
    },
    {
     "k": "Витрата палива",
     "v": "7 л"
    }
   ],
   "price": 1000,
   "unit": "год"
  },
  {
   "id": "dor-1",
   "cat": "road",
   "name": "Автогрейдер SEM 919",
   "img": "media/park/dor-1.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "18 т"
    },
    {
     "k": "Відвал",
     "v": "4 м"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dor-2",
   "cat": "road",
   "name": "Котки дорожні та ґрунтові",
   "img": "media/park/dor-2.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "4, 6, 12, 18 т"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dor-3",
   "cat": "road",
   "name": "Асфальтоукладач гусеничний Vögele",
   "img": "media/park/dor-3.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "21 т"
    },
    {
     "k": "Витрата палива",
     "v": "7 л"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dor-4",
   "cat": "road",
   "name": "Мініекскаватор-навантажувач",
   "img": "media/park/dor-4.webp",
   "specs": [
    {
     "k": "Маса",
     "v": "4 т"
    }
   ],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dm-1",
   "cat": "crush",
   "name": "Мобільна дробарка Gasparin Impianti",
   "img": "media/park/dm-1.webp",
   "specs": [],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dm-2",
   "cat": "crush",
   "name": "Мобільна щокова дробарка Extec C12+",
   "img": "media/park/dm-2.webp",
   "specs": [],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dm-3",
   "cat": "crush",
   "name": "Мульчер на базі мінінавантажувача Gehl",
   "img": "media/park/dm-3.webp",
   "specs": [],
   "price": null,
   "unit": "год"
  },
  {
   "id": "dm-4",
   "cat": "crush",
   "name": "Мульчер Raptor 300",
   "img": "media/park/dm-4.webp",
   "specs": [],
   "price": null,
   "unit": "год"
  }
 ],
 "materials": [
  {
   "id": "sand-y",
   "group": "Пісок",
   "name": "Пісок кар’єрний жовтий",
   "price": 240,
   "unit": "м³",
   "img": "media/mat/mat-1.webp",
   "doc": "протокол випробувань, сертифікат"
  },
  {
   "id": "sand-w",
   "group": "Пісок",
   "name": "Пісок річковий митий білий",
   "price": 280,
   "unit": "м³",
   "img": "media/mat/mat-2.webp",
   "doc": "протокол випробувань, Кременчуцький річковий порт, 2024"
  },
  {
   "id": "gr-5-20",
   "group": "Щебінь гранітний",
   "name": "Фракція 5–20 мм",
   "price": 640,
   "unit": "т",
   "img": "media/mat/mat-3.webp",
   "doc": "паспорт якості, фракція 5–20"
  },
  {
   "id": "gr-20-40",
   "group": "Щебінь гранітний",
   "name": "Фракція 20–40 мм",
   "price": 540,
   "unit": "т",
   "img": "media/mat/mat-4.webp",
   "doc": "паспорт якості, фракція 20–40"
  },
  {
   "id": "gr-40-70",
   "group": "Щебінь гранітний",
   "name": "Фракція 40–70 мм",
   "price": 540,
   "unit": "т",
   "img": "media/mat/mat-5.webp",
   "doc": "паспорт якості, фракція 40–70"
  },
  {
   "id": "otsiv",
   "group": "Щебінь гранітний",
   "name": "Відсів гранітний",
   "price": 420,
   "unit": "т",
   "img": "media/mat/mat-6.webp",
   "doc": "паспорт якості, фракція 0–5"
  },
  {
   "id": "shps",
   "group": "Суміші",
   "name": "ЩПС 0–40, 0–70",
   "price": 490,
   "unit": "т",
   "img": "media/mat/mat-7.webp",
   "doc": "сертифікат відповідності С7/С5"
  },
  {
   "id": "but",
   "group": "Суміші",
   "name": "Бутовий камінь",
   "price": 690,
   "unit": "т",
   "img": "media/mat/mat-8.webp",
   "doc": "паспорт якості"
  }
 ],
 "trailers": [
  {
   "maxT": 40,
   "rate": 100,
   "name": "Трал 40 т"
  },
  {
   "maxT": 60,
   "rate": 140,
   "name": "Трал 60 т"
  }
 ],
 "jobs": [
  {
   "id": "voda",
   "t": "Очищення водойм",
   "v": "Амфібія заходить туди, куди берегова техніка не дійде.",
   "b": [
    "Днопоглиблення",
    "Мул, очерет, корчі",
    "Намив земснарядом"
   ],
   "img": "media/svc/u-4.webp",
   "req": "rent",
   "subject": "Екскаватор-амфібія",
   "video": "job-voda"
  },
  {
   "id": "zemlia",
   "t": "Земляні роботи",
   "v": "Котлован, траншея, планування — рахуємо за зміну, не за обіцянки.",
   "b": [
    "Риття котлованів",
    "Розробка ґрунту",
    "Планування бульдозером"
   ],
   "img": "media/svc/u-1.webp",
   "req": "rent",
   "subject": "Гусеничний екскаватор 22 т",
   "video": "job-zemlia"
  },
  {
   "id": "trans",
   "t": "Перевезення негабариту",
   "v": "Трал 40 або 60 т — техніка на об’єкті в домовлений день.",
   "b": [
    "Трал до 60 т",
    "Вивіз будівельного сміття",
    "Пісок і щебінь самоскидами"
   ],
   "img": "media/svc/u-2.webp",
   "req": "transport",
   "subject": "Перевезення техніки тралом",
   "video": "job-trans"
  },
  {
   "id": "lis",
   "t": "Розчищення ділянок, корчування",
   "v": "Мульчер і дробарка замість бригади з пилами.",
   "b": [
    "Рубка дерев",
    "Корчування пнів",
    "Мульчування порослі"
   ],
   "img": "media/svc/u-3.webp",
   "req": "rent",
   "subject": "Мульчер",
   "video": "job-lis"
  },
  {
   "id": "demont",
   "t": "Демонтаж",
   "v": "Гідромолот, гідроножиці, кран — від стіни до вивозу.",
   "b": [
    "Знесення будівель",
    "Гідромолот, гідроножиці",
    "Розбирання завалів автокраном"
   ],
   "img": "media/svc/u-5.webp",
   "req": "rent",
   "subject": "Демонтаж: екскаватор із гідромолотом",
   "video": "job-demont"
  }
 ],
 "proof": [
  {
   "video": "proof-amph",
   "poster": "media/video/proof-amph.webp",
   "t": "Екскаватор-амфібія",
   "s": "очищення заболоченої ділянки, Полтавщина",
   "url": "https://www.tiktok.com/@poltavabudtehnika/video/7625991020492098837"
  },
  {
   "video": "proof-long",
   "poster": "media/video/proof-long.webp",
   "t": "Довгорукий екскаватор",
   "s": "«тут вода знову стане прозорою»",
   "url": "https://www.tiktok.com/@poltavabudtehnika/video/7579201889854606604"
  },
  {
   "video": "proof-sunset",
   "poster": "media/video/proof-sunset.webp",
   "t": "Hyundai на тралі",
   "s": "доставка амфібії на об’єкт",
   "url": "https://www.tiktok.com/@poltavabudtehnika/video/7688658909661334805"
  },
  {
   "video": "proof-trailer",
   "poster": "media/video/proof-trailer.webp",
   "t": "MAN + трал 60 т",
   "s": "JCB JS260 їде на об’єкт",
   "url": "https://www.tiktok.com/@poltavabudtehnika/video/7638993833958722837"
  },
  {
   "video": "proof-night",
   "poster": "media/video/proof-night.webp",
   "t": "Нічна зміна",
   "s": "техніка працює 24/7",
   "url": "https://www.tiktok.com/@poltavabudtehnika/video/7600714811185401108"
  },
  {
   "video": "proof-winter",
   "poster": "media/video/proof-winter.webp",
   "t": "Зима — не пауза",
   "s": "розчищення взимку",
   "url": "https://www.tiktok.com/@poltavabudtehnika/video/7588156683126459659"
  }
 ],
 "partners": [
  "media/logo/partners-1.webp",
  "media/logo/partners-2.webp",
  "media/logo/partners-3.webp",
  "media/logo/partners-4.webp",
  "media/logo/partners-5.webp",
  "media/logo/partners-6.webp",
  "media/logo/partners-7.webp",
  "media/logo/partners-8.webp",
  "media/logo/partners-9.webp",
  "media/logo/partners-10.webp",
  "media/logo/partners-11.webp",
  "media/logo/partners-12.webp",
  "media/logo/partners-13.webp",
  "media/logo/partners-16.webp",
  "media/logo/partners-17.webp",
  "media/logo/partners-18.webp",
  "media/logo/partners-19.webp"
 ],
 "regions": [
  "Полтавська",
  "Черкаська",
  "Дніпропетровська",
  "Харківська",
  "Запорізька",
  "Київська",
  "Кіровоградська",
  "Чернігівська",
  "Житомирська"
 ],
 "video": "media/video/"
};
