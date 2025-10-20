@echo off
title 🔄 LocoCraft Bot - Full Auto Update
echo.
echo 🚀 Wrzucam zmiany do GitHuba i uruchamiam automatyczny redeploy na Render...
echo.

:: --- KROK 1: GitHub update ---
git add .
git commit -m "Auto update - %date% %time%"
git push origin main

:: --- KROK 2: Wywołanie redeploy przez API Render ---
echo.
echo 🔁 Wymuszam redeploy na Render...
curl -X POST "https://api.render.com/v1/services/usr-d3rahnhr0fns73cs2q6g/deploys" ^
     -H "Accept: application/json" ^
     -H "Authorization: Bearer rnd_UYNacssSNbpGxJDA31E173gruEQz"

:: --- KROK 3: (opcjonalnie) reset cache ---
echo.
echo 🧹 Czyszczenie cache na Render... (jeśli włączone)
curl -X DELETE "https://api.render.com/v1/services/usr-d3rahnhr0fns73cs2q6g/caches" ^
     -H "Accept: application/json" ^
     -H "Authorization: Bearer rnd_UYNacssSNbpGxJDA31E173gruEQz"

:: --- KROK 4: Gotowe ---
echo.
echo ✅ Aktualizacja zakończona! Render został zrestartowany.
echo 🔧 Sprawdź postęp na stronie: https://render.com/dashboard
echo.
pause
