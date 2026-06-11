# Proyecto demo: Mariana — Ingeniera senior en busca de su Ikigai

> ℹ️ La data de este demo (tulipan.jsonl, intersection_concepts.yaml,
> visualizations/) vive como package data en
> [`ikigai/_demo_data/`](../../ikigai/_demo_data/) — single source of
> truth, accesible desde el wheel via importlib.resources.

## Cómo verlo

La forma soportada para usuarios pip-install:

```bash
ikigai init mi-demo/ --demo
ikigai serve mi-demo/ --open
```

Eso bootstrapea un copy del demo en `mi-demo/` y arranca el server.
Funciona igual de bien clonando el repo o instalando desde PyPI interno.

## Personaje

**Mariana** es una ingeniera senior en una empresa de tecnología. Ama enseñar, es
buena con arquitectura de sistemas, ve que faltan mentores para las
nuevas generaciones, y le pagan por liderar diseños técnicos. Su Ikigai
converge en una frase: **diseñar claridad para otros**.

Sus items incluyen:

- **Solo amor**: tocar guitarra, leer sci-fi
- **Solo habilidad**: hojas de cálculo gigantes, memoria de nombres
- **Solo mundo**: programa de reciclaje, huella de carbono
- **Solo pago**: Jira tickets, reportes de status
- **Pasión** (amo+bueno): cocinar pasta los domingos
- **Misión** (amo+mundo): voluntariado con perros
- **Profesión** (bueno+pago): código Python idiomatico
- **Trabajo necesario** (mundo+pago): mantener monolito legacy
- **Casi-Ikigai vocación**: inclusión de mujeres en STEM
- **Centro** (los 4): mentorear ingenieros junior en arquitectura

## Qué muestra

- **`/cuestionario`** — los 8 lados de los 4 cuadrantes (sembrados)
- **`/inventario`** — los 23 items de Mariana, taggeados a sus círculos
- **`/sintesis`** — el árbol de 14 cards con sus nombres acuñados:
  - 4 primitivos: `lo-que-me-llena`, `lo-que-fluye`, etc.
  - 6 pares: `pasion-domesticada`, `mision-personal`, `hobby-rentable`...
  - 4 casi-Ikigai: `vocacion-sin-pago`, `causa-justa`...
  - 1 centro: `diseñar-claridad-para-otros`
- **`/visualizador`** — el Venn de 4 círculos con las palabras de Mariana
