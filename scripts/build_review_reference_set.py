"""Build a frozen real-review reference set with independently curated labels.

The labels are Codex-assisted reference annotations, not human annotations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.config import ROOT
from src.database.connection import connect
from src.llm.review_tagger import validate_tags


def t(category,sentiment,evidence):
    return {"category":category,"sentiment":sentiment,"evidence":evidence}


ANNOTATIONS={
1056811604367718163:[t("location","positive","fantastic location"),t("value","positive","Unbelievable for the price and time of year")],
438130315:[t("location","positive","Excellent stylish space close to Botany Bay and Captain Cook’s landing place in South Sydney")],
597343150237464904:[t("location","positive","Perfect location just steps off the main strip")],
1509919044283888069:[t("host_service","positive","Samuel and Mereke were incredibly helpful"),t("location","positive","Location is absolutely great")],
612136478:[t("location","positive","Great location"),t("amenities","positive","Amazing pool and view from the roof top")],
55711094:[t("noise","positive","quiet area"),t("location","positive","2 mins from buzz of Potts Point"),t("host_service","positive","Rosslyn is an amazing host")],
1088789224204891307:[t("location","positive","Great location and very close to train stations, cafes and restaurants"),t("amenities","positive","The room itself is also very spacious"),t("host_service","positive","Ben and Stefano were fantastic hosts"),t("noise","negative","there is a bit of car/traffic noise")],
1155406700675642673:[t("noise","positive","lovely leafy, quiet neighbourhood"),t("amenities","positive","stylish, modern furnishings and everything you need for a comfortable stay"),t("host_service","positive","Prompt and regular communication from Made Comfy")],
1032966873243159061:[t("location","positive","great location (easy access to public transit, but a quiet neighborhood)"),t("noise","positive","quiet neighborhood"),t("host_service","positive","Craig was a friendly, generous, and responsive host")],
579259957859603956:[t("location","positive","Handy to eastern suburbs, shops and public transport"),t("amenities","positive","Comfortable room"),t("noise","positive","quiet")],
853926685294527235:[t("cleanliness","positive","Clean"),t("amenities","positive","comfortable"),t("value","positive","great value"),t("location","positive","Good location close to Redfern station")],
1259866468156044306:[t("cleanliness","positive","Our two main priorities are cleanliness and an accurate description of the accommodation. Both were ticked and there were no surprises."),t("accuracy","positive","Our two main priorities are cleanliness and an accurate description of the accommodation. Both were ticked and there were no surprises.")],
1662075759275580731:[t("host_service","positive","Ngoc is very responsive to any enquiries"),t("cleanliness","positive","The house is clean"),t("accuracy","positive","match to the descriptions")],
1587378829702692154:[t("amenities","positive","very spacious"),t("cleanliness","positive","clean apartment")],
795952152515286225:[t("location","positive","Beautiful location"),t("cleanliness","negative","The apartment is not the cleanest though. The coffee machine was moldy and smelled of cheese; definitely had not been cleaned in a while."),t("value","negative","for the price you are paying, you assume some kitchen or bathroom essentials would be provided"),t("amenities","negative","you must buy or bring everything")],
668233970:[t("host_service","positive","Verity was very hospitable and kind"),t("value","positive","Definitely worth the stay")],
1373565947963802625:[t("amenities","positive","It had everything we needed"),t("cleanliness","positive","clean and tidy"),t("host_service","positive","Gabriel’s communication was fantastic"),t("value","positive","Worth every cent")],
508938016621172430:[t("value","positive","Amazing value"),t("location","positive","great location"),t("host_service","positive","the staff are lovely and helpful")],
1304773968014061561:[t("location","positive","Location for concerts or footy fine"),t("cleanliness","negative","Bedding sheets were unclean"),t("amenities","negative","Bed was not made from last visitor"),t("value","negative","But for price of cleaning. Terrible")],
1702629531717431406:[t("location","positive","Such a perfect location"),t("host_service","positive","very accomodating host"),t("value","positive","definitely not overpriced")],
315082:[t("amenities","positive","We had everything we needed at our disposal"),t("host_service","positive","our hosts were kind to check in with us every now and then")],
54951252:[t("cleanliness","positive","clean and tidy"),t("location","positive","Close to public transport"),t("host_service","positive","The host is nice")],
958359880325144790:[t("host_service","positive","Pinky is friendly and helpful whenever I have questions")],
1466389176566164864:[t("host_service","positive","From first contact with the host everything was super simple"),t("location","positive","Great location directly opposite beach and minutes walk from loads of restaurants and cafes")],
1354013045035520437:[t("host_service","positive","The communicate and help was amazing. So helpful")],
1683076275868332092:[t("amenities","positive","very comfortable and I felt right at home. Plenty of utensils and kitchen space")],
232716478:[t("noise","positive","quiet and leafy location"),t("location","positive","moments away from the harbour and ferry"),t("amenities","mixed","The kitchen and bathroom are small but stylishly renovated")],
606114618746772041:[t("amenities","positive","comfortable two-bedroom cottage (one queen bed and two singles) with well-equipped kitchen"),t("cleanliness","positive","spotlessly clean"),t("safety","positive","Felt private and safe"),t("host_service","positive","Great communication")],
1332243911760788162:[t("location","positive","really convenient location"),t("amenities","positive","Air conditioner worked well, and the kitchen had everything we needed to prepare our meals. Beds were nice and comfortable")],
1404069129019332342:[t("amenities","positive","lovely views, pool"),t("location","positive","walking distance to transport & restaurants")],
1459114755885146912:[t("location","positive","close to the city but still peaceful"),t("cleanliness","positive","super clean"),t("accuracy","positive","looked like the photos")],
1264847374923570209:[t("location","positive","Close walk to park, pier and central area. Lots of restaurants walking distance"),t("accuracy","positive","Apartment was exactly like photos"),t("cleanliness","positive","clean"),t("amenities","positive","had everything necessary for a short comfortable stay")],
1235860629036960284:[t("host_service","positive","Christine and Geoff really put in the effort with lots of thoughtful touches"),t("amenities","positive","I really enjoyed the supplies to get you started in the morning"),t("accuracy","positive","Excellent stay as advertised")],
1651892197353497528:[t("amenities","positive","The appartment was very large for 2 bedrooms. The living areas were also bigger than expected."),t("location","positive","Location with easy access to airport and M8/M5 was perfect"),t("value","positive","extremely well priced")],
1189451836099135295:[t("cleanliness","positive","it's clean"),t("accuracy","positive","matched the description"),t("host_service","positive","Alan also was very nice and helpful")],
1589567651421763867:[t("safety","positive","Nice and safe Location"),t("amenities","positive","Spacious apartment that is fully equipped")],
1501920667368414000:[t("host_service","positive","quick to respond when i messaged them"),t("amenities","negative","the key is not in the lock box")],
1554064282317476796:[t("amenities","positive","The home was very pet friendly and the yard was perfect"),t("safety","positive","secure even for a small pup")],
1703421758411113605:[t("location","positive","Great location in Newtown , about a block off the Main Street ,close to bus and train")],
964855520537901571:[t("safety","positive","safe, quiet neighborhood"),t("noise","positive","quiet neighborhood"),t("location","positive","tons of bus lines to the CBD very close to the house"),t("accuracy","positive","exactly as described"),t("amenities","positive","such a comfortable, big bed"),t("host_service","positive","Jenny was a wonderful host. She was so welcoming and friendly")],
1517867160183131523:[t("location","positive","location is super handy to all the tourist hot spots"),t("amenities","positive","Beds were comfortable and apartment was spacious"),t("host_service","positive","Tommy was kind to let us check in early"),t("noise","negative","we had noisy neighbours from a different building with was frustrating at 3am")],
1301054618393395893:[t("location","positive","location was superb"),t("cleanliness","negative","needs some updating and proper cleaning. The place was dusty and all the mirrors were smeared"),t("amenities","negative","the bathroom really needs to be upgraded with an extractor fan")],
1099579126448949302:[t("value","mixed","The price of over $700 a night was absolutely not worth it. Its what you expect to pay at a 5 star resort. But.... like every other accommodation in Sydney and Melbourne for Taylor Swift the price was increased dramatically. <br/>Would I stay here again? Absolutely I would at the regular rate."),t("location","positive","Fantastic location"),t("host_service","positive","very friendly staff"),t("amenities","positive","the apartment had everything we needed")],
875622449224697514:[t("amenities","negative","the room air conditioner is not working at all"),t("host_service","negative","receptionist asked me to stay somewhere else when I feedback that the room air conditioner is not working at all. Bad service attitude")],
1089443173871025284:[t("location","positive","Good location for us on this trip"),t("amenities","negative","Disappointed that there’s no Air Conditioning, a fan doesn’t quite cut it at 30+. <br/>Also disappointed that tea and coffee was not provided")],
1404017619641415040:[t("accuracy","negative","The photos advertised did not match the apartment layout in person"),t("cleanliness","negative","The place was also infested with cockroaches and bugs everywhere")],
1288743755073556764:[t("safety","negative","the hotel is not secure/safe as s.o.p. is to leave a side door open with door stop 24 hrs"),t("host_service","negative","the desk clerks are transient so don’t care about the level of service they provide"),t("amenities","negative","the hot water is scarce")],
820543128809547092:[t("location","positive","Super Location in centre of Bondi road"),t("accuracy","negative","photos were quite misleading in terms of space"),t("safety","negative","Tiles on bathroom floor had lifted and were quite dangerous if bare footed"),t("value","negative","we felt it was extremely over priced for what it was"),t("host_service","positive","Maria was very easy to communicate with")],
1375795672929699994:[t("location","positive","Location awesome"),t("amenities","positive","comfy pillows, air con great"),t("cleanliness","negative","smelly(very musky), bed dirty(had re wash ourselves)"),t("value","negative","high cleaning fee"),t("accuracy","negative","misleading about security"),t("host_service","negative","host not helpful(no apology or assistance for dirty arrival)")],
1545356194874437409:[t("value","positive","fits the budget"),t("safety","negative","the area feels a bit unsafe at night")],
610204213:[],
365943479:[],
1389541814937964793:[],
1637385879081795331:[],
906860712417838492:[],
}


def main():
    ids=list(ANNOTATIONS)
    placeholders=",".join("?" for _ in ids)
    with connect() as connection:
        rows=connection.execute(
            f"SELECT review_id, comments FROM reviews_clean WHERE review_id IN ({placeholders})",ids
        ).fetchall()
    comments={int(review_id):str(text) for review_id,text in rows}
    missing=set(ids)-set(comments)
    if missing:
        raise RuntimeError(f"Missing source reviews: {sorted(missing)}")
    payload=[]
    for review_id,tags in ANNOTATIONS.items():
        item={"review_id":review_id,"comments":comments[review_id],"expected_tags":tags}
        validate_tags({"reviews":[{"review_id":review_id,"tags":tags}]},[item])
        payload.append(item)
    if len(payload)!=55:
        raise RuntimeError(f"Expected 55 reviews, got {len(payload)}")
    dataset=ROOT/"evaluation/review_reference_v1.json"
    raw=(json.dumps(payload,ensure_ascii=False,indent=2)+"\n").encode()
    dataset.write_bytes(raw)
    prompt=ROOT/"prompts/review_tagger.txt"
    manifest={
        "version":"review_reference_v1",
        "status":"frozen_before_live_run",
        "source":"Inside Airbnb Sydney 2026-06-16 real public snapshot",
        "annotation_provenance":"Codex-assisted curated reference labels; not human-labelled",
        "review_count":len(payload),
        "tag_count":sum(len(x["expected_tags"]) for x in payload),
        "dataset_sha256":hashlib.sha256(raw).hexdigest(),
        "prompt_sha256_at_freeze":hashlib.sha256(prompt.read_bytes()).hexdigest(),
    }
    (ROOT/"evaluation/review_reference_v1_manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n"
    )
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
