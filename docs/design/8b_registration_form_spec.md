# 8b 창작자 등록 (Font Registration) — Design Specification Extract

**Source**: `/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html`  
**Lines**: 386–408  
**Frame Label**: 8b 창작자 등록 (/submit)

---

## SECTION A: Layout Skeleton

```
┌─ Card (width: 480px) ─────────────────────────────────┐
│                                                          │
│ ┌─ Header (gap:10px, padding:16px 28px) ──────────────┐│
│ │ [SVG Triangle Icon] Font A git                       ││
│ └──────────────────────────────────────────────────────┘│
│                                                          │
│ ┌─ Content (padding:30px 28px) ──────────────────────┐ │
│ │                                                      │ │
│ │ 폰트 등록 신청                                       │ │
│ │ (Page title: h1, 800 24px)                         │ │
│ │                                                      │ │
│ │ 만드신 폰트를 아지트에 소개해 주세요.               │ │
│ │ 검토 후 등록됩니다.                                 │ │
│ │ (Lead text: 400 13px/1.6, color:#6B6B6B)          │ │
│ │                                                      │ │
│ │ [Form fields - flex column, gap:16px]              │ │
│ │                                                      │ │
│ │ 1. Font Name field                                  │ │
│ │ 2. [2-col grid] Creator | Classification            │ │
│ │ 3. Official Page URL field                          │ │
│ │ 4. License toggle buttons                           │ │
│ │ 5. Submit button                                    │ │
│ │                                                      │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## SECTION B: Form Fields — Verbatim Labels & Inputs (IN ORDER)

| # | Field Label (Label Text) | Required | Input Type | Placeholder/Value | Helper Text | Notes |
|---|---|---|---|---|---|---|
| 1 | **폰트 이름** | ✓ (red *) | text input | 예: 아지트 고딕 | — | Single-column |
| 2a | **제작자** (in 2-col grid) | ✓ (red *) | text input | 이름/팀 | — | Left column |
| 2b | **분류** (in 2-col grid) | ✗ | select dropdown | 고딕 | ▾ | Right column; grid gap:12px |
| 3 | **공식 페이지 URL** | ✓ (red *) | text input | https:// | — | Single-column |
| 4 | **라이선스** | ✗ | toggle buttons | — | — | 3 options: 무료 (Free, selected), 유료 (Paid), 조건부 (Conditional) |
| — | **신청 보내기** | — | button | — | — | Green button, margin-top:6px |

### Field-by-field breakdown:

**1. 폰트 이름** (Font Name)
- Label: "폰트 이름 " + required marker (red *2C5545)
- Input: height 44px, border-radius 10px, border #E6E6E2
- Placeholder: "예: 아지트 고딕"
- Padding: 0 14px (horizontal), vertically centered

**2a. 제작자** (Creator)  — Left column of 2-col grid
- Label: "제작자 " + required marker (red *)
- Input: height 44px, same style as field 1
- Placeholder: "이름/팀"

**2b. 분류** (Classification) — Right column of 2-col grid
- Label: "분류" (no required marker)
- Input: height 44px, select dropdown style
- Display value: "고딕" (default)
- Dropdown indicator: "▾" (right-aligned)
- Grid container: display:grid, grid-template-columns:1fr 1fr, gap:12px

**3. 공식 페이지 URL** (Official Page URL)
- Label: "공식 페이지 URL " + required marker (red *)
- Input: height 44px, same style
- Placeholder: "https://"

**4. 라이선스** (License)
- Label: "라이선스" (no required marker)
- Input type: Three toggle buttons (flex row, gap:8px)
  - Button 1: "무료" (Free) — **SELECTED state**: border #2C5545, color #2C5545
  - Button 2: "유료" (Paid) — unselected: border #E6E6E2, color #6B6B6B
  - Button 3: "조건부" (Conditional) — unselected: border #E6E6E2, color #6B6B6B
- Button style: padding 8px 14px, border-radius 20px, font 500 12px

**Submit Button: 신청 보내기** (Send Application)
- Background: #2C5545 (green)
- Color: #fff (white text)
- Height: 48px
- Font: 600 14px
- Border-radius: 11px
- Margin-top: 6px
- Full width (100%)

---

## SECTION C: Sizing & Spacing

| Element | Size/Value |
|---|---|
| Card width | 480px |
| Card border-radius | (inherited from card class) |
| Header padding | 16px 28px |
| Header height | (auto, fits icon + text) |
| Content padding | 30px 28px |
| Form field gap | 16px (flex-direction: column) |
| Field height | 44px |
| Field border-radius | 10px |
| Field padding (h) | 0 14px |
| Field border width | 1px |
| Label font | 600 12px 'Pretendard', sans-serif |
| Input font | 400 13px 'Pretendard', sans-serif |
| Label-to-input gap | 7px (margin-bottom on label) |
| License button padding | 8px 14px |
| License button border-radius | 20px |
| License button font | 500 12px |
| 2-col grid gap | 12px (gap between creator & classification columns) |
| Button height | 48px |
| Button font | 600 14px 'Pretendard', sans-serif |
| Button border-radius | 11px |
| Button margin-top | 6px |
| Page title (h1) | 800 24px, color #1A1A1A, letter-spacing -.02em, margin 0 0 6px |
| Lead text (p) | 400 13px/1.6, color #6B6B6B, margin 0 0 24px |

### Color palette:
- Primary green: #2C5545
- Light gray (bg): #FAFAF8
- Border: #E6E6E2
- Text (primary): #1A1A1A
- Text (secondary): #6B6B6B
- Text (placeholder): #9A9A96
- White (input bg): #fff

---

## SECTION D: Validation & State Styling

**Normal state** (as shown):
- All fields: border #E6E6E2, 1px solid
- All text: color #1A1A1A or #9A9A96 (placeholder)

**License toggle**:
- **Selected** ("무료" in mockup): 
  - border: 1px solid #2C5545
  - color (text): #2C5545
  - background: transparent (implied)
- **Unselected**: 
  - border: 1px solid #E6E6E2
  - color (text): #6B6B6B
  - background: transparent

**Required field marker**:
- Displayed as red asterisk "*" in color #2C5545
- Positioned inline in label

**No explicit error/success states shown in 8b mockup**  
(Design shows happy-path form only; error states not rendered in this frame)

---

## SECTION E: Mobile & Dark Mode Notes

### Mobile variant (4x frames):
- **4b is NOT the submit form** — it shows font detail/preview page on mobile (label: "상세 · 모바일")
- No dedicated mobile mockup for 8b registration form found in design file
- **Implication for dev**: Treat desktop 480px as reference; apply responsive design (single-col stack, max-width, touch-friendly 48px+ tap targets)

### Dark mode variant:
- **9b is NOT the submit form** — it's the dark-mode home page
- No dark-mode 8b registered variant in design file  
**Implication for dev**: Either (1) dark mode uses inverted palette on same form structure, or (2) dark mode form is pending design. Recommend using CSS dark-scheme variables and testing contrast.

---

## SUMMARY FOR IMPLEMENTATION

| Aspect | Value |
|---|---|
| Frame ID | 8b |
| URL path | /submit |
| Layout type | Single-column form card |
| Card width | 480px |
| Form fields (total) | 5 input groups + 1 submit button |
| Required fields | 3 (폰트 이름, 제작자, 공식 페이지 URL) |
| Optional fields | 2 (분류, 라이선스) |
| Primary CTA | 신청 보내기 (green #2C5545) |
| Primary font | Pretendard |
| Border radius (inputs) | 10px |
| Border radius (button) | 11px |
| Mobile support | No explicit mockup; assume responsive flex stack |
| Dark mode | No explicit mockup; assume palette swap required |

