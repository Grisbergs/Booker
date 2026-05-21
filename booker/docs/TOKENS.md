# Design Tokens

## Primary Palette

| Token | Hex | Use |
|------|-----|-----|
| primary-900 | #021B1A | Background |
| primary-800 | #032221 | Surfaces |
| primary-700 | #03624C | Headers |
| primary-600 | #007B81 | Links |
| primary-500 | #2CC295 | Primary actions |
| primary-50  | #F1F7F6 | Light background |

---

## Secondary Palette

| Token | Hex | Use |
|------|-----|-----|
| secondary-900 | #06302B | Deep UI |
| secondary-800 | #0B453A | Borders |
| secondary-700 | #095544 | Hover |
| secondary-600 | #17876D | Success |
| secondary-500 | #2FA98C | Accent |

---

## Neutrals

| Token | Hex | Use |
|------|-----|-----|
| neutral-500 | #707D7D | Secondary text |
| neutral-300 | #AACBC4 | Borders |

---

## Light Theme
- Background: #F1F7F6
- Surface: #FFFFFF
- Text: #021B1A
- Border: #AACBC4

---

## Dark Theme
- Background: #021B1A
- Surface: #032221
- Text: #F1F7F6
- Border: #095544

---

## CSS Variables Strategy

Use:

```css
:root {
  --bg: #F1F7F6;
  --surface: #FFFFFF;
  --primary: #2CC295;
}