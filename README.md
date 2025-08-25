# Discord Sales Bot (Modular)


## Rodando local
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env && edite os valores
python -m src.main


## Postar produto na vitrine
No Discord, em um canal de vitrine (ex.: #loja-8ball), rode:
!postar_produto 8BALL_GUIDE_PRO