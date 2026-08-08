import os, re
for fname in sorted(os.listdir("templates/emails")):
 if not fname.endswith(".html"): continue
 with open(f"templates/emails/{fname}","r",encoding="utf-8") as f:
  content = f.read()
 hex_colors = re.findall(r"#[0-9a-fA-F]{6}", content)
 inline_styles = re.findall(r'style="[^"]*"', content)
 style_tags = len(re.findall(r"<style[^>]*>", content))
 style_in_head = "style" in content.split("</head>")[0] if "</head>" in content else False
 print(f"{fname}: hex={len(hex_colors)} inline={len(inline_styles)} tags={style_tags} head={style_in_head}")