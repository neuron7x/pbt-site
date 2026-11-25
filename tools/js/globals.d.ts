// Глобальні точки зв'язку між скриптами сторінки (web/js/*.js): дані, модулі й прапорці збірки.
interface Window {
  PBT: any;
  PBT_CINE?: any;
  PBT_BUNDLE?: boolean;
  PBTQuote?: any;
  PBTBlueprint?: any;
  PBTDom: any;
  PBTPhysics: any;
  PBTcalc?: any;
  PBTv?: any;
}
interface Navigator { connection?: { saveData?: boolean; effectiveType?: string } }
interface Window { trustedTypes?: { createPolicy(name: string, rules: { createScriptURL?: (u: string) => string }): { createScriptURL(u: string): unknown } } }
