# Centralised image URL registry.
# All imgur (and future CDN) URLs live here — never hardcode them elsewhere.

# ── NPC PORTRAITS (for embed.set_author — square-ish headshots work best) ─────
# These are intentionally kept as full CDN URLs for easy reuse as author icons.
AMARA_PORTRAIT = (
    "https://cdn.discordapp.com/attachments/1334637411363323996"
    "/1509665755707215992/guildmaster_amara.jpg"
    "?ex=6a1a014c&is=6a18afcc"
    "&hm=0e213ea0757113d5ec7d3f6cad0ebd458b57d804e4f0a413d3146487b74ad8c5&"
)

MAID_SPRITZ_PORTRAIT = (
    "https://cdn.discordapp.com/attachments/1334637411363323996"
    "/1514311718191239328/maid_portrait.jpg"
    "?ex=6a2ae830&is=6a2996b0"
    "&hm=6816908585f7847f37d4c4747a97f7bca203aa73324e8afefce0d7aee36c329c&"
)

# ── AUTHOR PORTRAITS (larger dedicated headshots for embed.set_thumbnail) ─────
# These are the primary portraits used for NPC "voice" on embeds.
# Previously small icons were passed to set_author(icon_url=...); we now use
# set_thumbnail() with these for better visibility + set_author(name=...) only.
AMARA_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321498754646038/amara_portrait.jpg?ex=6a2af14c&is=6a299fcc&hm=1acbc5a03498b012818174eef8e4122e5aad9dbacb8d2fe626c41712ff535675&"
QUEST_SHOP_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321500193423420/quest_shop_portrait.jpg?ex=6a2af14c&is=6a299fcc&hm=58e3fda24dcf189e3832e2c28dc217dcc66c42f0240623eeca65c678a32c721e&"
SLAYER_MASTER_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321500415463494/slayer_master_portrait.jpeg?ex=6a2af14c&is=6a299fcc&hm=fbfcaa46508bb3e13f0dec144de832b8d7c6120ef02e1c16e27b2f49000d3f9f&"
BAR_MAID_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321498968690708/bar_maid_portrait.jpeg?ex=6a2af14c&is=6a299fcc&hm=5649bc84fe4d78f518254f06d14d4f35cf45982a2db5b75418b281ec346b98d6&"
CASINO_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684191238553690/tavern_casino_portrait.jpg?ex=6a372d0c&is=6a35db8c&hm=1aa7a8ac9120dee24bed1853792d12749be7d99504d6649c92ccf26eea7ea03a&"
POTION_SHOP_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321499975061624/potion_shop_portrait.jpg?ex=6a2af14c&is=6a299fcc&hm=a6d7c0231f772865d4c2da884f8d917a9898d2751bd3bac93821fa7170c3e3b1&"
HARLAN_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321499765477488/harlan_portrait.jpeg?ex=6a2af14c&is=6a299fcc&hm=572eb27722eb196242aae16fee3a06fc279aea7742d4021c8307294a19e0b5cb&"
SYLAS_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321500679966791/sylas_portrait.jpg?ex=6a2af14c&is=6a299fcc&hm=a8b86fd26be5eeffe95d8d25e9888165a61287d2dc85a7d7d0b06c26c69e2bb7&"
VEYRA_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321500977627148/veyra_portrait.jpg?ex=6a2af14c&is=6a299fcc&hm=de9016cfb9c45f214e8365ab2cf4a186a3985b5c607358fbc7a74d73dbc75f68&"
BLACK_MARKET_AUTHOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1514321499266355240/black_market_portrait.jpg?ex=6a2af14c&is=6a299fcc&hm=e0cd77b18b1ec8778d46092983f7149747b19b379008e2fe9c051c56cc128a97&"

# Convenience alias for the maid portrait (already defined above)
MAID_AUTHOR = MAID_SPRITZ_PORTRAIT

LUCIEN_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328761257857145/apex_hunter_lucien.jpg?ex=6a35e207&is=6a349087&hm=815b60b5f828b6b2fe134e5528e622c8bdc965741e23d9cff74a6bae6d4d3748&"
LUCIEN_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328761572425838/apex_hunter_lucien_portrait.jpg?ex=6a35e207&is=6a349087&hm=54f082f0571526026868f79191fb2a506a3b21ab73842e77635971b9da2a47c9&"

SERAPHINE_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328761832476682/seraphine_grand_archivist.jpg?ex=6a35e207&is=6a349087&hm=921d64e5c9e50f19fada53265956901023f65c4dc46ab90606539f8cb4f092fd&"
SERAPHINE_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328762197377034/seraphine_grand_archivist_portrait.jpg?ex=6a35e207&is=6a349087&hm=03b2540289133608773733361e464dd952c5cb3701feb278d3e143dedc64da3e&"

VALE_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328762398576783/tower_warden_vale.jpg?ex=6a35e207&is=6a349087&hm=c145daa214c87dd66d42f76c638f380dae6d0a8336b965d13f9f517007a0447d&"
VALE_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328762604228669/tower_warden_vale_portrait.jpg?ex=6a35e207&is=6a349087&hm=2700770b6baed0be7cdd82d974f84585307c409c6f8a1d70d58ba866f934500d&"

YUNA_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328762906083360/yuna_master_tamer.jpg?ex=6a35e207&is=6a349087&hm=2dc743d0ea0c08d05d303b2441dea3c03b696330ff055b38fc40d36304f4975d&"
YUNA_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517328763153551451/yuna_master_tamer_portrait.jpg?ex=6a35e207&is=6a349087&hm=9b6c178f8b469536185a7de8d6489853ab88bae34e31714a54667636e353ae3f&"

BROTHER_SOLEN_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684189862953120/brother_solen.jpg?ex=6a372d0c&is=6a35db8c&hm=5ced23795533c23ffbf0a666d86158ad0d3a96c4477e0a54b8fa784326c4f0b0&"
BROTHER_SOLEN_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684190085382294/brother_solen_portrait.jpg?ex=6a372d0c&is=6a35db8c&hm=6aa6f7c6d228cf53f3eca04597cc024d32b8f67a6c82b8073c634d69c09942be&"

RAGNA_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684190315941998/ragna_fleshwright.jpg?ex=6a372d0c&is=6a35db8c&hm=c5582838f9b4975d9fd0c5572270b48933b7432470bf8b24338e4376570f91a6&"
RAGNA_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684190567727325/ragna_fleshwright_portrait.jpg?ex=6a372d0c&is=6a35db8c&hm=78326ccf42e6bf66f8936d1d90088069e024d972af758c5f9ba894b71a17592e&"

VALDRIS_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684199648399490/valdris_sanguine.jpg?ex=6a372d0e&is=6a35db8e&hm=8ac796c4c4466c5c8b1b9808bb5b0f4dd307ed1dd766b7f2f93877b3b7d99f6d&"
VALDRIS_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684199878950912/valdris_sanguine_portrait.jpg?ex=6a372d0e&is=6a35db8e&hm=d859bb50794fa64c3c753b29b7c53adb0bfcfdfc95c7645d5b5639bb85815fc5&"

ARBITER_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684189325951079/arbiter_uber.jpg?ex=6a372d0b&is=6a35db8b&hm=73261c4096d46f3908020d3a5dab2b3216c0c391bd8e57d27290606678df7446&"
ARBITER_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684189594521691/arbiter_uber_portrait.jpg?ex=6a372d0c&is=6a35db8c&hm=d6f3d514a0979214c777b11057f67d9f9d537317d8058941d2463c3b1c5af407&"

TESSARA_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684191674896384/tessara_lapidary.jpg?ex=6a372d0c&is=6a35db8c&hm=d658e0bb24bc7c85df495988027ba5cd6d16397b1f4cf5865af4a2f5fae62001&"
TESSARA_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684191926419476/tessara_lapidary_portrait.jpg?ex=6a372d0c&is=6a35db8c&hm=02bf22c965b775160c5ab2f48efce90edc46f1c4aeee6c11e86f453d2bb2fe19&"

ELIZA_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1524391542804975686/prestige_vendor.jpg?ex=6a4f93c1&is=6a4e4241&hm=fc19ec93fa4a24f987ec225d92a694223a5199316aa9e03b875ac93d9f66e017&"
ELIZA_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1524391543023206561/prestige_vendor_profile.jpg?ex=6a4f93c1&is=6a4e4241&hm=13b54f4955129130e6dd3161611345ae9e68242b3425eedfabf90a0095ab94e4&"

# ── COMBAT ────────────────────────────────────────────────────────────────────
COMBAT_VICTORY = "https://cdn.discordapp.com/attachments/1334637411363323996/1521926282831724674/combat_victory.png?ex=6a469bcd&is=6a454a4d&hm=dc26b97e719a462648394e6988d92487bb4e069139823a775ef5590fd74774a2&"
COMBAT_REDEMPTION = "https://cdn.discordapp.com/attachments/1334637411363323996/1521926291178262649/combat_redemption.png?ex=6a469bcf&is=6a454a4f&hm=f0084a2b079e1126beb4e0c9d1a058a518654ce16e6f160345dd041aadfb5d07&"
COMBAT_ELEMENTAL = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512647081361730/combat_elemental.png?ex=69f8b4cd&is=69f7634d&hm=51af5a2214e2ddedcae29fe6fc52f4113669b2a2a77120c181f8a479b71a6a26&"
COMBAT_DUMMY = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512846797213838/commoner_f.png?ex=69f8b4fc&is=69f7637c&hm=65b9cf447b2c8fc98dadeab8f21692279631f496c79dc9d1e526fc67ec99a899&"
COMBAT_LOW_HEALTH = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523688075890708/COMBAT_LOW_HEALTH.jpg?ex=6a123657&is=6a10e4d7&hm=1084f405af2092a55216f5ae245f102ffc6d3f679183e0963dea63ae5435efed&"

# ── BOSS PET PORTRAITS ────────────────────────────────────────────────────────────
# Shared between uber-entry embeds and in-combat pet thumbnails.
BOSS_APHRODITE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512847120171179/boss_aphrodite.jpeg?ex=69f8b4fc&is=69f7637c&hm=19f9a7010b27f757393a38bf96229a267c4b4d90005906b52eb16a1f66e6a2f8&"
BOSS_LUCIFER = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512847564898396/boss_lucifer.png?ex=69f8b4fd&is=69f7637d&hm=48834029b0438c566ac4bb049b739ae58862f1e514a33cd5e47a689115d6c9d1&"
BOSS_NEET = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512848034529412/boss_neet.png?ex=69f8b4fd&is=69f7637d&hm=c47a8d4b4b7e667f00b43af41b4e3b5798f83745755b586dfdf62b17677ffc99&"
BOSS_GEMINI = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512848458027189/boss_gemini.png?ex=69f8b4fd&is=69f7637d&hm=ef0070f97a24cb04cf1a99d42df1ee1b6a86d8e09d1c9e93210471102524ec97&"  # uber-entry portrait
BOSS_GEMINI_PET = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512849221521588/boss_gemini_pet.jpeg?ex=69f8b4fd&is=69f7637d&hm=324393488026d621c611a02de84f23e24fec964a3b332579e99378f8bc007f7c&"  # in-combat pet

# Animated variants used as Section/Thumbnail accessories in UberHubView (one per boss slot).
BOSS_APHRODITE_ANIM = "https://cdn.discordapp.com/attachments/1334637411363323996/1524772570417598494/uber_aphro_anim.gif?ex=6a50f69d&is=6a4fa51d&hm=2ae9d28381fc52854690ce909799095f6d9a8e0c70081e41774d945920bc1812&"
BOSS_EVELYNN_ANIM = "https://cdn.discordapp.com/attachments/1334637411363323996/1524772578743554200/uber_eve_anim.gif?ex=6a50f69f&is=6a4fa51f&hm=0d9950ce96948c9a5da1e3fceb40ca15ac9c60385e8a61dd25bd7dcbc089f2b6&"
BOSS_GEMINI_ANIM = "https://cdn.discordapp.com/attachments/1334637411363323996/1524772586456748155/uber_gemini_anim.gif?ex=6a50f6a1&is=6a4fa521&hm=7b8598fa14a9a155d86a6c71e847a896bee8ef84239c35a8a5f063b4a267b8f8&"
BOSS_NEET_ANIM = "https://cdn.discordapp.com/attachments/1334637411363323996/1524772594660933652/uber_neet_anim.gif?ex=6a50f6a3&is=6a4fa523&hm=a1b160a531ec79cc399ab584dcd3fb2e2d346e2eb94eaefa593469e155aca478&"
BOSS_LUCIFER_ANIM = "https://cdn.discordapp.com/attachments/1334637411363323996/1524773647863255081/uber_lucifer_anim.gif?ex=6a50f79e&is=6a4fa61e&hm=0853f4e90611c77faef04cf48f5c06414b4de30d89790f02caaa738f369be015&"

# ── UBER BOSS MONSTER IMAGES (set on Monster.image, shown in combat embeds) ────────
MONSTER_APHRODITE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512849729032354/monster_aphrodite.jpeg?ex=69f8b4fd&is=69f7637d&hm=9e8d92508b4afa68ed37ae90b215ef84543abf46e77888b2bd9dd245c5383140&"
MONSTER_LUCIFER = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512850135744654/monster_lucifer.jpeg?ex=69f8b4fd&is=69f7637d&hm=e02fcc19942992b88f1b7b3ba32a2aa2e04e393131e913668cb4ea4bcffe431d&"
MONSTER_NEET = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512850614161528/monster_neet.jpeg?ex=69f8b4fd&is=69f7637d&hm=e46ec818e6ee38e464844230b7b8200bbc96928e4015ed4ef1967c649428f28c&"
MONSTER_GEMINI = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512851100438660/monster_gemini.jpeg?ex=69f8b4fd&is=69f7637d&hm=105cade5215b913fd9d2c758ad422d9f1b7ce5940fc423d712aa91c5d89b870b&"
MONSTER_EVELYNN_PRECURSOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1501338062142181548/evelynn_precursor.jpg?ex=69fbb587&is=69fa6407&hm=37b45bd41af8c58c63e5e07a2e049a4dea8a566463fdc612fd59a5a30a6824da&"
MONSTER_EVELYNN = "https://cdn.discordapp.com/attachments/1334637411363323996/1501338061878071466/evelynn.jpg?ex=69fbb587&is=69fa6407&hm=70291f73eba57fc7f170babfd0cbe37b8a8507c98a2687b8af8231c13265bd90&"

# ── THE RITE OF CONVERGENCE — WING MONSTER IMAGES (Monster.image per wing) ─────
MONSTER_APHRODITE_REBORN = "https://cdn.discordapp.com/attachments/1334637411363323996/1525264671790075964/aphro_reborn.gif?ex=6a52c0eb&is=6a516f6b&hm=3ff8154efc7cfd2b1918cc06ad90a3589af7d5f1c5f18d8dea089e0adf72c7ad&"
MONSTER_LUCIFER_REBORN = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248417335607346/lucifer_reborn.gif?ex=6a52b1c8&is=6a516048&hm=f5d07b2902503e9c0b2fb658a8eb3ce10a0268a24a0cb94acababea07c22299e&"
MONSTER_GEMINI_REBORN = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248409705906338/gemini_reborn.gif?ex=6a52b1c6&is=6a516046&hm=6ae527eee0e3295fa9af318b7c95d29fc4828d4934247886af89328b41f9d621&"
# void_reborn.gif — NEET Reborn is the "Void"-species wing (see core/rite/mobgen.py: generate_wing_neet).
MONSTER_NEET_REBORN = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248455944048701/void_reborn.gif?ex=6a52b1d1&is=6a516051&hm=a54a19b235abe608756193fa3b8940fad81b7c50033771c2143a3a9d39b8782b&"
MONSTER_EVELYNN_REBORN = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248359500091493/evelynn_reborn.gif?ex=6a52b1ba&is=6a51603a&hm=eaba7d21f3350ad804c07a8dfbf77d3d3607d0c0d04ae87b79603a2fc8185265&"

# ── THE RITE OF CONVERGENCE — ARBITER PHASE IMAGES (phases 1-5, phase 6 final) ─
# Phase order matches ARBITER_PHASE_NAMES in core/rite/mobgen.py: Left Wing of
# the Heavens (angel), Right Wing of the Nine Hells (hell), Left Arm of
# Ultimate Balance (gemini), Right Arm of the Infinite Void (void), the
# converged Amalgam (final_form), then the true Arbiter reveal (final_fight).
ARBITER_PHASE_1 = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248312758763691/amalgam_angel_wing.gif?ex=6a52b1af&is=6a51602f&hm=c1ac318e405c6feca78b5e635ec4796a1d1b8ec689ca377b3d3efc5561b6d7dd&"
ARBITER_PHASE_2 = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248335240237287/amalgam_hell_wing.gif?ex=6a52b1b4&is=6a516034&hm=8482a3dc432f789bd096cb674bd2c59fd05f37cf667edc6cdcd90708c0455cdf&"
ARBITER_PHASE_3 = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248327745273956/amalgam_gemini_arm.gif?ex=6a52b1b3&is=6a516033&hm=ab91b124b0a5659f85db8098c458b79ab8b3e8bd00ef920cc707a08b3992b957&"
ARBITER_PHASE_4 = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248343373250790/amalgam_void_arm.gif?ex=6a52b1b6&is=6a516036&hm=635c78fec1941662a89ec27ef48a69b76140f376ad4dbb551de55fcb2b97ed0b&"
ARBITER_PHASE_5 = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248320312840312/amalgam_final_form.gif?ex=6a52b1b1&is=6a516031&hm=d60acd53d6aaaf462ec6fd9067646f46ffac10dcb0f26a2e01901228921b1b75&"
ARBITER_PHASE_FINAL = "https://cdn.discordapp.com/attachments/1334637411363323996/1525248351178723428/arbiter_final_fight.gif?ex=6a52b1b8&is=6a516038&hm=1702168ee8b79609920b1032ffa06c3589e390f23094402fbc9a0276447c2a7c&"

# ── THE RITE OF CONVERGENCE — ARTEFACT ICONS ────────────────────────────────────
# NOTE: no dedicated Gemini-themed asset has been provided yet for Seal of
# Duality — it currently falls back to MONSTER_GEMINI_REBORN in loot.py.
ARTEFACT_BLESSED_BULWARK = "https://cdn.discordapp.com/attachments/1334637411363323996/1524915641352589372/artefact_aphro.jpg?ex=6a517bdc&is=6a502a5c&hm=79f5face03af8b40c13c018a24808de31c26907e3f70bb2f4e4a0a7994c8c6bd&"
ARTEFACT_BRAND_OF_RUIN = "https://cdn.discordapp.com/attachments/1334637411363323996/1524915642224869458/artefact_lucifer.jpg?ex=6a517bdc&is=6a502a5c&hm=08103f9ae4ca11aab795120593ae9ef99fabfe4242c242c0cce7ff391f9adaff&"
ARTEFACT_SAD_ONES_GAMBLE = "https://cdn.discordapp.com/attachments/1334637411363323996/1524915642459881472/artefact_neet.jpg?ex=6a517bdc&is=6a502a5c&hm=68a81d4ff462b2c43317d90114babaccf852abd25bca58e6225e2952fab2448e&"
ARTEFACT_CORRUPTED_INSIGNIA = "https://cdn.discordapp.com/attachments/1334637411363323996/1524915641943986421/artefact_evelynn.jpg?ex=6a517bdc&is=6a502a5c&hm=19ae6d50e1dc8112b2c2d4c693a3395e11f1995ed7e6f199a2828b24f17363d7&"
ARTEFACT_THE_FINAL_EDICT = "https://cdn.discordapp.com/attachments/1334637411363323996/1524915641637933140/artefact_edict.jpg?ex=6a517bdc&is=6a502a5c&hm=2b026046dbc3202f13cf2dc2def513bb4a160b0580b930a7c42907951f44f866&"

# ── ENCOUNTER GATE IMAGES ─────────────────────────────────────────────────────
ENCOUNTER_ANGELIC_DRAGON = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512863390011623/encounter_angelic_dragon.png?ex=69f8b500&is=69f76380&hm=601ea2e1dc4f39e8259a8c513a2910922f696cc6777f2a95d0ba518de78baa93&"
ENCOUNTER_SOUL_CORE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512864002375872/encounter_soul_core.png?ex=69f8b500&is=69f76380&hm=80b9a61f0d6fe219bc23864f2856e8577d985c433eede16e58db74f2a4119d9d&"
ENCOUNTER_VOID_FRAGMENT = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512864450904105/encounter_void_fragment.jpeg?ex=69f8b501&is=69f76381&hm=d9cfbe8c46af9e7a65326029b5fd7b18e3fbdf28df2e1bb7e0fada6c833768e3&"
ENCOUNTER_BALANCE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512864727990463/encounter_balance.png?ex=69f8b501&is=69f76381&hm=dcbeeae99fb5ca16a3375f86ac51a5c2dc1b48046b572ac79767ef5856670c1e&"

# ── SKILLS / TOOLS ────────────────────────────────────────────────────────────
TOOL_PICKAXE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512865159872583/tool_pickaxe.jpeg?ex=69f8b501&is=69f76381&hm=cfe51d42df16b60dcf230ebe7e07a48b914548c2955d0aa573ed34b9935e9a3e&"
TOOL_AXE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512865591890001/tool_axe.jpeg?ex=69f8b501&is=69f76381&hm=007ddefe22197bc9d53cc9e0c9f3970eada4f71000e039b31de7224f1c6e464b&"
TOOL_ROD = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512866007257198/tool_rod.jpeg?ex=69f8b501&is=69f76381&hm=d6eb7024eba79a37b0f22c4e2c1d3a96291adc7ba9c40cbf62e52ab35939a1ce&"

# ── BOSS VICTORY SCREENS ──────────────────────────────────────────────────────
VICTORY_APHRODITE_GEMINI = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512866405584996/victory_aphrodite_gemini.jpg?ex=69f8b501&is=69f76381&hm=f9af57b6c3154275b1ae72649693c79fd296051899a4370efa3bb35ce652de16&"
VICTORY_NEET = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512866845855837/victory_neet.jpeg?ex=69f8b501&is=69f76381&hm=5290351b6746158ef934548ba1f80f845a51b6f0987587bfbeeb2fe05d73346e&"
VICTORY_LUCIFER = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512867483521034/victory_lucifer.jpeg?ex=69f8b501&is=69f76381&hm=fe627bc77bfd6930581c9df79b52fce3c4ee642cf31c8a4613b6e4d929813c5a&"
VICTORY_CELESTIAL = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512875700027422/victory_celestial.jpeg?ex=69f8b503&is=69f76383&hm=8b1fa916ad630664c977340841282d391fadd794b8016a9ea120d04992f5c817&"
VICTORY_INFERNAL = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512876035833926/victory_infernal.png?ex=69f8b503&is=69f76383&hm=abb14094c913e145e1d5b1928c73133796f3666f45c730db9172dab8116f907e&"
VICTORY_GEMINI = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512876346081483/victory_gemini.jpeg?ex=69f8b503&is=69f76383&hm=bc54c5729840e79f9a27a87241b17b04219d53a21d5a59bcdb665713d8106909&"
VICTORY_EVELYNN = "https://cdn.discordapp.com/attachments/1334637411363323996/1501338062452428890/evenlynn_defeat.jpg?ex=69fbb587&is=69fa6407&hm=c5fad31341630838537a52dba8aba728062798a207b2043e5a615572712e6c68&"

# ── UBER HUB ──────────────────────────────────────────────────────────────────
UBER_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523699362889799/UBER_HUB.jpg?ex=6a12365a&is=6a10e4da&hm=5a486678bf142e476fcdfdb4a6e1bc02f3a29fbcb87d25c7985e594ceaaa3764&"

# ── INVENTORY ─────────────────────────────────────────────────────────────────
INVENTORY_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512876656333003/inventory_hub.png?ex=69f8b503&is=69f76383&hm=bea347681384e86f5d2f7dd03cd946c0e6a108627478eec004395b111cca5077&"

# ── INVENTORY / EQUIPMENT SLOTS ───────────────────────────────────────────────
SLOT_WEAPON = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512877256380488/slot_weapon.jpeg?ex=69f8b504&is=69f76384&hm=231bec20bccbac9beb14af7d14c52b61ee59e27eccd6560301a960d45a09c78c&"
SLOT_ARMOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512877503709314/slot_armor.jpeg?ex=69f8b504&is=69f76384&hm=7875e6f296a843baf556b1f268b981e152d6751370bdb6734ee54f11451dc8e9&"
SLOT_HELMET = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512877801640016/slot_helmet.jpeg?ex=69f8b504&is=69f76384&hm=cef84163be40261fd8cd41f6b666cecb1730f45ddd72c0ed99ff82b0dff59350&"
SLOT_GLOVE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512878103498853/slot_glove.jpeg?ex=69f8b504&is=69f76384&hm=2b13b2e86b01254e3f77f82067682b6d866b035da36e9f97af60ef818d9e48d0&"
SLOT_BOOT = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512878393032714/slot_boot.jpeg?ex=69f8b504&is=69f76384&hm=60153f43f3301954c91fe3ccdc6451db30da0212ab2d870b2f0894374ffc088c&"
SLOT_ACCESSORY = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512878657015978/slot_accessory.jpeg?ex=69f8b504&is=69f76384&hm=f1797e2afbe74150c6404120a4dc376dbda8a19fae778fed5313eb708b4f2d78&"

# ── UPGRADE / FORGE ───────────────────────────────────────────────────────────
UPGRADE_FORGE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512887033167912/upgrade_forge.jpeg?ex=69f8b506&is=69f76386&hm=c29c6db44bd9f82f88911b0e691835e07884808f0deecb9c1625771a19e0499a&"
UPGRADE_REFINE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512887297540298/upgrade_refine.jpeg?ex=69f8b506&is=69f76386&hm=894365cbfb79d2ada9c2490713f0efe0ef26ea261ba932967fb9f22752545ba2&"
UPGRADE_ENCHANT = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512887645405284/upgrade_enchant.jpeg?ex=69f8b506&is=69f76386&hm=78aa51dbed82c67d75fa049b8df2134db9610b04fb872ed19504ec9680de93a4&"
UPGRADE_TEMPER = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512888027091055/upgrade_temper.png?ex=69f8b506&is=69f76386&hm=399f3341b9ed28870eae0f6152706ba7efda20291b36e420c2743f5113ea0903&"
UPGRADE_VOIDFORGE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512888505368726/upgrade_voidforge.jpeg?ex=69f8b506&is=69f76386&hm=0861f9ec2699a2b062dbeb8f7e3c5110d765d20269076b1597ca6164c555231c&"
UPGRADE_REINFORCE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512888958226452/upgrade_reinforce.jpeg?ex=69f8b506&is=69f76386&hm=8643191002f0618a3979195635ed8e399207a3269d92cb8c8d18d4fbaa1d136c&"
UPGRADE_INFERNAL_ENGRAM = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512889306615939/upgrade_infernal_engram.jpeg?ex=69f8b506&is=69f76386&hm=8f4cf3c3b57b7003933efea3161a4d221bd8e3b41060d52dbca30916a007315b&"
UPGRADE_GEMINI_ENGRAM = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512889570721822/upgrade_gemini_engram.jpeg?ex=69f8b507&is=69f76387&hm=42f67d4ee1b40c091d83ac15c38d5eaa1a97bf39e2c30ba4986b16a41a9600b6&"
UPGRADE_VOID_ENGRAM = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512889864196206/upgrade_void_engram.jpeg?ex=69f8b507&is=69f76387&hm=4068a3451ee24db227ba3a948f74c3c6fd6631d3cb99b57377cdb0fb3d0af8ca&"
UPGRADE_CELESTIAL_ENGRAM = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512890216513587/upgrade_celestial_engram.jpeg?ex=69f8b507&is=69f76387&hm=f167eee54fef7f0069c08a59c2976da49c163a0e61cba166e93e6261e9ecfe61&"

# ── CURIOS ────────────────────────────────────────────────────────────────────
CURIO_UNOPENED = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512900584968202/curio_unopened.jpeg?ex=69f8b509&is=69f76389&hm=7c3b66af3db495c385674e5e811dfea9e7c6b84fa136ddc1b9e08a5f923b2c20&"
CURIO_BULK = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512900912250891/curio_bulk.jpeg?ex=69f8b509&is=69f76389&hm=9b8b8dee6c3116097d589dd53231332222463c0931463a9dd32aa21d1478fb20&"
CURIO_PUZZLE_BOX = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512901373497434/curio_puzzle_box.jpeg?ex=69f8b509&is=69f76389&hm=da75273cca058cc1568f2bddf9d78a6a10da86617d1f395ad8f3804e4d45a702&"

# ── ALCHEMY ───────────────────────────────────────────────────────────────────
ALCHEMY_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512901767889046/alchemy_hub.png?ex=69f8b509&is=69f76389&hm=94fd4553150fd35994f99b0545167463f80846ec531d5f9809a863e8443c87e6&"
ELYNDRA_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1517257938555637991/master_alchemist_elyndra.jpg?ex=6a35a011&is=6a344e91&hm=78d689b0a7b92dbcc1e9b2c16e8a43e83203cec016f02e0b27e7c44e43eec402&"
ELYNDRA_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1517257938836787380/master_alchemist_elyndra_portrait.jpg?ex=6a35a011&is=6a344e91&hm=e0ffa48f740c8dc1e5e5ede9862b9b9f3b6f683e46f07e7f8cbdbe54c422e54c&"

# ── ESSENCE ───────────────────────────────────────────────────────────────────
ESSENCE_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523688818282577/ESSENCE_HUB.jpg?ex=6a123657&is=6a10e4d7&hm=bbb43a95b64dd49bd25b825afa93eb3d9d7cc03aa64535b350ad5ba6e9d8de0f&"

# ── ASCENT ────────────────────────────────────────────────────────────────────
ASCENT_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512902308696144/ascent_hub.jpeg?ex=69f8b50a&is=69f7638a&hm=9f32e2587fcdcdf1efbe3ae2d36a089ba611ff4fcc05255e85455cc15c646896&"

# ── HEMATURGY ─────────────────────────────────────────────────────────────────
HEMATURGY = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398699545301032/hematurgy.jpg?ex=6a0e1e9d&is=6a0ccd1d&hm=5ae101bc4cfe9be3aad04ec654d1e64f1dacbcacba89da0716e5b3c48b63b360&"

# ── CODEX ─────────────────────────────────────────────────────────────────────
CODEX_BOON = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512902715670548/codex_boon.png?ex=69f8b50a&is=69f7638a&hm=0be68b2c4045894fe8ee57d49b53499c3206940e986121fdffd66e9ca2cbe2a2&"
CODEX_CHAPTERS = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512903261065389/codex_chapters.png?ex=69f8b50a&is=69f7638a&hm=304ab6be2813c21f79b1663ae2a8d879b2d117afe2411ffa8899962d8785d2d4&"
CODEX_TOME = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512903688622110/codex_tome.png?ex=69f8b50a&is=69f7638a&hm=787e6f6a5dfb3436922902cf7e8e39031832429a3b25bfdeff0332130688f297&"
CODEX_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512904192200874/codex_hub.png?ex=69f8b50a&is=69f7638a&hm=401e138fa9056db9e032dd18c19a42037eb595c97a3d9a1747d91f48069b5852&"

# ── CONSUME ───────────────────────────────────────────────────────────────────
CONSUME_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512904842313799/consume_hub.jpeg?ex=69f8b50a&is=69f7638a&hm=1da8939721bafefeaac308ce9efeee748fe81590f9b81a6d75ec1c6070009863&"
CONSUME_EGG = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398698597519392/consume_egg.jpg?ex=6a0e1e9d&is=6a0ccd1d&hm=2db7f0a505bb5408eb759a56a4ad0bbdb480b7b996bbedc4a37a47a0a2539655&"

# ── CONSUME / MONSTER PARTS ───────────────────────────────────────────────────
CONSUME_MONSTER_HEAD = "https://cdn.discordapp.com/attachments/1334637411363323996/1505042264898932857/monster_head.jpg?ex=6a092f56&is=6a07ddd6&hm=c098e8bf9ae9a01ce82091701df8e4e8cd95b15514fe69ef3e50b80ac1272a7b&"
CONSUME_MONSTER_TORSO = "https://cdn.discordapp.com/attachments/1334637411363323996/1505042284784259172/monster_torso.jpg?ex=6a092f5b&is=6a07dddb&hm=bfff4f8d48c40f60fb78305ebb0ed1f59a1a7a18a7cac1cd9fbc3759124724f4&"
CONSUME_MONSTER_ARM = "https://cdn.discordapp.com/attachments/1334637411363323996/1505042250114011307/monster_arm.jpg?ex=6a092f52&is=6a07ddd2&hm=f9fb1611e234005295666a4eb6569433bc2ffae176fc446c621076d76d38f22e&"
CONSUME_MONSTER_LEG = "https://cdn.discordapp.com/attachments/1334637411363323996/1505042271333253350/monster_leg.jpg?ex=6a092f57&is=6a07ddd7&hm=215330b4c6f5c44deb4400a2c2272418f904d512557b57d0cf588b524218e89c&"
CONSUME_MONSTER_CHEEKS = "https://cdn.discordapp.com/attachments/1334637411363323996/1505042257894572153/monster_cheeks.jpg?ex=6a092f54&is=6a07ddd4&hm=00207c7fb5881924ad09d45b1064598ff08b26ad6603219b5cce066d9ed7327e&"
CONSUME_MONSTER_ORGANS = "https://cdn.discordapp.com/attachments/1334637411363323996/1505042278220304424/monster_organs.jpg?ex=6a092f59&is=6a07ddd9&hm=8b427cbf608ec8b00b62b3aaa89382c027104b1624503a3a82eeca2e7f130cbe&"

CONSUME_SLOT_IMAGES = {
    "head": CONSUME_MONSTER_HEAD,
    "torso": CONSUME_MONSTER_TORSO,
    "right_arm": CONSUME_MONSTER_ARM,
    "left_arm": CONSUME_MONSTER_ARM,
    "right_leg": CONSUME_MONSTER_LEG,
    "left_leg": CONSUME_MONSTER_LEG,
    "cheeks": CONSUME_MONSTER_CHEEKS,
    "organs": CONSUME_MONSTER_ORGANS,
}

# ── COMPANIONS ────────────────────────────────────────────────────────────────
COMPANIONS_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512917202796564/companions_hub.png?ex=69f8b50d&is=69f7638d&hm=1c354bba4eb0c9d1d27d64ffe4d3ab920c03efe965d3c1895f6b64f772fdaf79&"
COMPANIONS_FUSION = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523688294121564/COMPANIONS_FUSION.jpg?ex=6a123657&is=6a10e4d7&hm=083e05f9b5088579ce623511e6c279b0ac308601728472b39931748273c2708d&"

# ── DELVE ─────────────────────────────────────────────────────────────────────
DELVE_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512917676888305/delve_hub.png?ex=69f8b50d&is=69f7638d&hm=42667dbdb8f454fafad8e2647449dcac43a3e2fba84509f3a660d2ff6fc239d4&"
DELVE_MAIN = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512918121349190/delve_main.png?ex=69f8b50d&is=69f7638d&hm=cd725b9626fe981fa67d972724627421487fd1734f2dcb02a7f872253eac1544&"
DELVE_REWARDS = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512918574202900/delve_rewards.png?ex=69f8b50d&is=69f7638d&hm=d0e75adb784d74d3ac798841b58161f2261c9df356a804adc3ef7f23d4b799e8&"
DELVE_MINING = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512919027454052/delve_mining.png?ex=69f8b50e&is=69f7638e&hm=d194c11ccb30220bacca402c9e5076e262b3962fbb5cfd5fb23ebeece135c160&"

# ── DUELS ─────────────────────────────────────────────────────────────────────
DUELS_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512919413198909/duels_hub.jpeg?ex=69f8b50e&is=69f7638e&hm=652fed163b832e7c827c9dcf8b75ed5dbcb17493e1aeaa023716ddd48a9bd1dd&"

# ── TRADE ─────────────────────────────────────────────────────────────────────
TRADE_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523699144921219/TRADE_HUB.jpg?ex=6a12365a&is=6a10e4da&hm=e25c6887e24f0d7738957d1f8c0eead38a4585bf87c2e109ce3ac2b36bf31363&"

# ── LEADERBOARD ───────────────────────────────────────────────────────────────
LEADERBOARD_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523697706274937/LEADERBOARD_HUB.jpg?ex=6a123659&is=6a10e4d9&hm=23e913494529326377526afd9cd76aabc0e19986ff531ddf912838bad6a7127b&"

# ── PRESTIGE ──────────────────────────────────────────────────────────────────
PRESTIGE_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523698360586401/PRESTIGE_HUB.jpg?ex=6a12365a&is=6a10e4da&hm=3f263fcd49ba4c85898864f940415385dd1b126e1784e5d554de2f6fc0d288f2&"
PRESTIGE_HALL = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523698117185626/PRESTIGE_HALL.jpg?ex=6a12365a&is=6a10e4da&hm=1e15849d55e45eaf2904265d9ec2d4d36e0582fc2db32f8274825039183ed613&"

# ── APEX HUNT ─────────────────────────────────────────────────────────────────
APEX_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523687174246400/APEX_HUB.jpg?ex=6a123657&is=6a10e4d7&hm=943f7fa792682748b9d8874850cb630cc23d39e6d349bfb52b2f1ecb34fcc32c&"
APEX_SOUL_STONE = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523687631421580/APEX_SOUL_STONE.jpg?ex=6a123657&is=6a10e4d7&hm=060b5171280b58d125ce4669d8425957871794492e8fb5a95ab112019b7db8df&"
APEX_IMPRINT = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523687417385070/APEX_IMPRINT.jpg?ex=6a123657&is=6a10e4d7&hm=006ce6577fe06ecee368d8ea4dbd15cc007f7ea465f49ce3ec8f1ae2f80dfc4e&"
APEX_UPGRADE = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523687853723648/APEX_UPGRADE.jpg?ex=6a123657&is=6a10e4d7&hm=33b10244926a9ae8ab45693a8690c845fe0f99c80b3db85f6df87da8b18afa22&"

# ── EVENTS ────────────────────────────────────────────────────────────────────
EVENT_ASTEROID = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512919857922239/event_asteroid.png?ex=69f8b50e&is=69f7638e&hm=1577635ad0ccced8fdfca4b5db5eaf6097f1009d8530a0653580297f4bfc47f2&"
EVENT_LEPRECHAUN = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512920298197012/event_leprechaun.png?ex=69f8b50e&is=69f7638e&hm=59bfd4b4102a593e52c4670b90253bbb4e25ec133a72571b23bdbb046519591e&"
EVENT_DRYAD = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512920717758664/event_dryad.png?ex=69f8b50e&is=69f7638e&hm=6a6e78d54122ae8bb34b356c5cbcd9725cd1487873bf9a44235ec52b919f605d&"
EVENT_TIDE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512921178996958/event_tide.png?ex=69f8b50e&is=69f7638e&hm=775afe2649add3c02b2a5de4d266bcad5be43de87287e0a7d37dea5beeab37bb&"

# ── MAW ───────────────────────────────────────────────────────────────────────
MAW_MAIN = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512932491170023/maw_main.jpeg?ex=69f8b511&is=69f76391&hm=6901fe61134f29c908ac93bff99e4848a4ada945774cd8c0d2c72b9699a3381e&"
MAW_VICTORY = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512932780572803/maw_victory.jpeg?ex=69f8b511&is=69f76391&hm=efb1ac48d3dfb175da86580e3fb489158f7cfd04aa030e03821865129db740f1&"

# ── PARTNERS ──────────────────────────────────────────────────────────────────
PARTNERS_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512933178769539/partners_hub.jpeg?ex=69f8b511&is=69f76391&hm=4311ac5b558ded4d186cd7e5ea9eb1b9bbee147414aa5a7289d904ba67933845&"
PARTNERS_DISPATCH = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512933577490493/partners_dispatch.jpeg?ex=69f8b511&is=69f76391&hm=5ee4d38ad41fe733aa31588decd48ea16f77c1aa74832d479a5903c06fc35982&"
PARTNERS_MALE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512934319755465/partners_male.jpeg?ex=69f8b511&is=69f76391&hm=3311fd4e1aa676b4a324d1327d5064808811d04df17818b31e005493eabf4af5&"
PARTNERS_FEMALE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512934558695434/partners_female.jpeg?ex=69f8b511&is=69f76391&hm=a5c9c9106ac8505b66c7a5fca9e6e6fac2ed788d298a7746638bb9b57ca8fff9&"
PARTNERS_BOSS_PARTY = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512934885855393/partners_boss_party.jpeg?ex=69f8b511&is=69f76391&hm=52208047795e976985692729a64ff28d967444fbeba499f5c18ad5314117f6bc&"
PARTNERS_INTRO = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512935137775817/partners_intro.jpeg?ex=69f8b511&is=69f76391&hm=e2b78dba4721c22201f2da3f80a23078d15fe43a72c7457b4a20bf8a1ab67f0c&"
PARTNERS_SKILLS = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512935448150026/partners_skills.jpeg?ex=69f8b511&is=69f76391&hm=d8a8251544872d44925eaeb6175f8ff0a792a96b391786c4338aeb9cb7be5dcb&"
# Partner affinity story images (one per story tier, 4 per partner)
EVE_AFFINITY_1 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612101461872721/eve_affinity_1.jpg?ex=6a19cf54&is=6a187dd4&hm=db300ee0e6ec4c142501fe2d293fb30bd2f0ff7a74f1726e7f89aa7f2a0a6613&"
EVE_AFFINITY_2 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612101705011440/eve_affinity_2.jpg?ex=6a19cf54&is=6a187dd4&hm=c629797840d2d3c423d5d86b78d78d626988ad66887c71d67fb44c58507b6d96&"
EVE_AFFINITY_3 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612101960990761/eve_affinity_3.jpg?ex=6a19cf54&is=6a187dd4&hm=3b74ba71c56b630f86f0b296e380453081682daceb4ca97a1b3962828abf0d5e&"
EVE_AFFINITY_4 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612102191419442/eve_affinity_4.jpg?ex=6a19cf54&is=6a187dd4&hm=53849de9a63de8b8ab6dfb1ce99d69a1cee0358cb5d8eae6f51503721db45c04&"
KAY_AFFINITY_1 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612111272349876/kay_affinity_1.jpg?ex=6a19cf56&is=6a187dd6&hm=34b8fce01bbc321a8350f59d731b7030561dcc6bb5898e7bf03a3689bf6bc6a9&"
KAY_AFFINITY_2 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612111570141367/kay_affinity_2.jpg?ex=6a19cf56&is=6a187dd6&hm=293d82d257bc20b73af1106453a405d254f33d5237379d0e4129e0b8c436ede2&"
KAY_AFFINITY_3 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612111817478254/kay_affinity_3.jpg?ex=6a19cf56&is=6a187dd6&hm=7cc198970203b583e475ab067650c7afbd919b1c6e1381d89815c30a0330282b&"
KAY_AFFINITY_4 = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612112048033992/kay_affinity_4.jpg?ex=6a19cf56&is=6a187dd6&hm=1dbfaa623958f387844bd3bc80bc4c2caac694afc4936da9daa60cbbe13199ae&"

GACHA_BANNER_4STAR = "https://cdn.discordapp.com/attachments/1334637411363323996/1500515435366453398/gacha_banner_4star.jpeg?ex=69f8b766&is=69f765e6&hm=5fe2ae5da2c45d30614f747158ff7197b64502a8a64dc5094836b156fe007208&"
GACHA_BANNER_5STAR = "https://cdn.discordapp.com/attachments/1334637411363323996/1500515435714445343/gacha_banner_5star.jpeg?ex=69f8b766&is=69f765e6&hm=8ad7e30c8acbfb3b3c3147f15dcf7052607db308603728c1e453eadcee5d6010&"
GACHA_BANNER_6STAR = "https://cdn.discordapp.com/attachments/1334637411363323996/1500515436054446341/gacha_banner_6star.jpeg?ex=69f8b766&is=69f765e6&hm=4c521c1fc1d5f8daffc4b813fa8a59d150cc8ba16da7b6d01f01c83ea0667374&"

# ── SETTLEMENT ────────────────────────────────────────────────────────────────
SETTLEMENT_CONSTRUCTION = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512935745949777/settlement_hub.png?ex=69f8b512&is=69f76392&hm=9de3f1fbe984f1d5920139c291a431ff079b6afeb0b59a66cfe5d74fad8c28ad&"
SETTLEMENT_HUB = SETTLEMENT_CONSTRUCTION  # backward-compat alias
SETTLEMENT_BUILDINGS = {
    "town_hall": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512947166777546/town_hall.png?ex=69f8b514&is=69f76394&hm=2c2d76de14655f2d02a4a3a76b77522f2244ed8546057dc17f5e2d958e56ad2d&",
    "logging_camp": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512947531944107/logging_camp.png?ex=69f8b514&is=69f76394&hm=6c07eda02de100c0ffc4ac4bf55f2679f21c777b4de14cac315d76fb9f9cf9ee&",
    "quarry": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512947888455841/quarry.png?ex=69f8b514&is=69f76394&hm=fb5340212e9b68b4d8de442661b08e689a4692299246220f272dbd3f5ad23446&",
    "foundry": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512957656858624/foundry.png?ex=69f8b517&is=69f76397&hm=fa1c04e144931075d410fb821892f50f949e345aa0288ddac7201ce01a6e8c79&",
    "sawmill": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512958084681768/sawmill.png?ex=69f8b517&is=69f76397&hm=2e7fe8dc463e34a5ea5c4b6c7d5e948b5c1b0942c34d416007fceba685240c20&",
    "reliquary": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512958629937203/reliquary.png?ex=69f8b517&is=69f76397&hm=4b58bdf73a686f0c3128b0bc5b29b931ed0325918171cdebfaaae7be9939402b&",
    "market": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512959053431035/market.png?ex=69f8b517&is=69f76397&hm=d038d4a51864c7573196bc09760ee814897cdf159fb70bab74c8beed56648008&",
    "barracks": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512959644963138/barracks.png?ex=69f8b517&is=69f76397&hm=15cf1ef23382c70e6cb4a9c80575197e6749fee07cd056c6a288b161cedda294&",
    "temple": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512960274239799/temple.png?ex=69f8b517&is=69f76397&hm=9c8dae72cc8639210f2ac2215dbdaa4a481b0b1f4127292ad50b698de3174994&",
    "apothecary": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512960743866560/apothecary.png?ex=69f8b518&is=69f76398&hm=1f95d81508eb411e592a27705112aff92d35ca22e0ab5f4023cc0a1ff580ff48&",
    "black_market": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512961242992801/black_market.png?ex=69f8b518&is=69f76398&hm=385c50f0144a29313fcb7aaeb11c26e0dfb3fbf910e6d504fce8fedcbc28734a&",
    "companion_ranch": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512961599639762/companion_ranch.png?ex=69f8b518&is=69f76398&hm=5d419074c38d7915e96e7f72522888aabb4a53fa6539db27042a0842541b3354&",
    "celestial_shrine": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512960274239799/temple.png?ex=69f8b517&is=69f76397&hm=9c8dae72cc8639210f2ac2215dbdaa4a481b0b1f4127292ad50b698de3174994&",
    "infernal_shrine": "https://cdn.discordapp.com/attachments/1334637411363323996/1507523697446097056/infernal_forge.jpg?ex=6a123659&is=6a10e4d9&hm=9f0ca30b20906ea250be6fcef8f68c300d9b7e300473677a742aa6dc12d9ba0e&",
    "void_shrine": "https://cdn.discordapp.com/attachments/1334637411363323996/1507523688596115657/corrupted_shrine.jpg?ex=6a123657&is=6a10e4d7&hm=08da355b1f716e9f2119c865efb7a384582f7b9ddd00d7bccbd6908ebe8c5536&",
    "twin_shrine": "https://cdn.discordapp.com/attachments/1334637411363323996/1507523689057484950/gemini_shrine.jpg?ex=6a123657&is=6a10e4d7&hm=8c9630435050b94c891f8f4d25c079271d6aa3e7dcfd7832212ed30edfd0d601&",
    "hatchery": "https://cdn.discordapp.com/attachments/1334637411363323996/1507523698624692407/settlement_hatchery.jpg?ex=6a12365a&is=6a10e4da&hm=d0a8251cec847aeb834f51bb6d7cd66da98f834370099a9ee981bd3486474324&",
    # New buildings (reuse closest existing asset until custom art is added)
    "nursery": "https://cdn.discordapp.com/attachments/1334637411363323996/1514718987684937839/nursery.jpg?ex=6a2c637c&is=6a2b11fc&hm=f4c871d39d1858631a184362e29c37620a2ff0bf9647100a26d1227febc3c2d9",
    "idlem_foundry": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512957656858624/foundry.png?ex=69f8b517&is=69f76397&hm=fa1c04e144931075d410fb821892f50f949e345aa0288ddac7201ce01a6e8c79&",
    "uber_shrine": "https://cdn.discordapp.com/attachments/1334637411363323996/1500512960274239799/temple.png?ex=69f8b517&is=69f76397&hm=9c8dae72cc8639210f2ac2215dbdaa4a481b0b1f4127292ad50b698de3174994&",
}

# Settlement NPC portraits
SETTLEMENT_MAID = MAID_SPRITZ_PORTRAIT

# Crisis event monster images — keyed by spawn_combat value in SETTLEMENT_EVENTS
CRISIS_MONSTER_IMAGES: dict[str, str] = {
    "bandit_captain": "https://cdn.discordapp.com/attachments/1334637411363323996/1527037732235514006/bandit_captain.jpg?ex=6a593436&is=6a57e2b6&hm=5f3fbf313dd26a5898e034694a99623e219cf18bf374b42fefbcb2099facf874&",
    "ember_wraith": "https://cdn.discordapp.com/attachments/1334637411363323996/1527037732554146113/ember_wraith.jpg?ex=6a593436&is=6a57e2b6&hm=6c6781ed9262ba9813c5b29ffbdb24b169b0d40067579585304706ab6d7dc7fa&",
    "plague_wraith": "https://cdn.discordapp.com/attachments/1334637411363323996/1527037732889821204/plague_wraith.jpg?ex=6a593436&is=6a57e2b6&hm=c800cc008eadd83cc934068d09bfa7ffca2a2d5604d337910be1d9028f422afa&",
    "void_sentry": "https://cdn.discordapp.com/attachments/1334637411363323996/1527035271290425394/void_sentry.jpg?ex=6a5931eb&is=6a57e06b&hm=53a4193d1f803efd39ff93c8be5105f5be64bfc1c04b06eda615bea5df78bf99&",
}

# ── CORRUPTED MONSTERS ────────────────────────────────────────────────────────
# Dict keyed by monster name stem (without "corrupted_" prefix).
# Used in generate_corrupted_encounter() to set Monster.image.
CORRUPTION_GATE = "https://cdn.discordapp.com/attachments/1334637411363323996/1501335301468061746/corrupted_gate.jpg?ex=69fbb2f5&is=69fa6175&hm=6c365e05f54f49447013d7477cc7fce272f5801998452ff377e5721ba14a4747&"
CORRUPTED_MONSTERS = {
    "blessed_zealot": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262536048382202/corrupted_blessed_zealot.jpg?ex=69fb6f30&is=69fa1db0&hm=2c58f56956f6df7c1bc7e1a6a06c7bc78d6032a6afd1bc7cb9fb6dd358865c46&",
    "blossom_samurai": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262536501100686/corrupted_blossom_samurai.jpg?ex=69fb6f30&is=69fa1db0&hm=0b6356dca3d8239404f5d891b2263270484189af1d0f457201236a0d383732f6&",
    "chrono_prisoner": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262536912277554/corrupted_chrono_prisoner.jpg?ex=69fb6f30&is=69fa1db0&hm=a9aa776ae790b7d29e60a3f44c55c693c347da2ac99ac636f624ed03319535f5&",
    "dragon_princess": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262537260269698/corrupted_dragon_princess.jpg?ex=69fb6f30&is=69fa1db0&hm=0894f62885d8727946dc78292b82acccd2d4eee1b6b46c6af96392dd5c0dd192&",
    "ivory_succubus": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262537621246133/corrupted_ivory_succubus.jpg?ex=69fb6f31&is=69fa1db1&hm=8a0bc9f249f61ca0eb51ce28d838b483e0ef262ce032e53ab1010ef0dfebd9bd&",
    "lotus_oni_princess": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262537956528138/corrupted_lotus_oni_princess.jpg?ex=69fb6f31&is=69fa1db1&hm=79c3a0d919c3cc9c9ad63d3ce60f0de04eaabfc14fd7e0cd3dae0b0bbe5bddd0&",
    "sword_angel": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262538329948231/corrupted_sword_angel.jpg?ex=69fb6f31&is=69fa1db1&hm=2a49b0daf7429d1fec4da8403849cfc83ace8222edfa6c74011fd9351fbb8ce6&",
    "winged_swordsmaiden": "https://cdn.discordapp.com/attachments/1334637411363323996/1501262538703114481/corrupted_winged_swordsmaiden.jpg?ex=69fb6f31&is=69fa1db1&hm=4c99f4d1ba5bed1e5c7198751108954128102677adf1dd61aeb8aca32fd301bc&",
}

# ── SLAYER ────────────────────────────────────────────────────────────────────
SLAYER_MASTER = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512944839196672/slayer_master.jpeg?ex=69f8b514&is=69f76394&hm=80574a877f344b671995071e57369d25bec6f534fcbf943a6a8be049e9f0f1c2&"
SLAYER_EMBLEM = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512945111568566/slayer_emblem.png?ex=69f8b514&is=69f76394&hm=9e0e91ed0c4e0ba48c7283d29e5faf3dee64b01b3bc1b933a48527e8b9fd72bc&"

# ── QUESTS ────────────────────────────────────────────────────────────────────
QUEST_BOARD = "https://cdn.discordapp.com/attachments/1334637411363323996/1509665756294545558/quest_board.jpg?ex=6a1a014c&is=6a18afcc&hm=092888c4013254e6544ea5cef26d654afc6d99cc70c9ab39afdd55dd2ebdd6f6&"
QUEST_SHOP = "https://cdn.discordapp.com/attachments/1334637411363323996/1509665756802060429/quest_shop.jpg?ex=6a1a014c&is=6a18afcc&hm=703ba9cfd01f11b75d98d69e126b8cbbcb199fa05dc724c3a7dc788b84fee82e&"

# ── TAVERN / POTION SHOP ──────────────────────────────────────────────────────
POTION_SHOP = "https://cdn.discordapp.com/attachments/1334637411363323996/1509665756001079316/potion_shop.jpg?ex=6a1a014c&is=6a18afcc&hm=c5fa81b24406ce6d43a6264d30d2196fbdd871c0c377cae373c934e96d2ef8b4&"

# ── PARADISE JEWEL SKILLS ─────────────────────────────────────────────────────
SKILL_UNCUT = "https://cdn.discordapp.com/attachments/1334637411363323996/1506409619210375291/skill-uncut.jpg?ex=6a0e28c8&is=6a0cd748&hm=d6405a6ec77e08dff6454c264611585dcaad0dd1331b50055ccdadd309c415ed&"
SKILL_ACRIMONY = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398709829734662/skill-acrimony.jpg?ex=6a0e1e9f&is=6a0ccd1f&hm=276aac7c67999bbb61d9d3f8bf19c69bca55d7d0a3b2ab0055c78dd9635bc967&"
SKILL_BASTION = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398710114816102/skill-bastion.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=b1a210e6a692ce6b8df116f12b9d83198dbdc333773b35078765330db96e7d2e&"
SKILL_CATACLYSM = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398710484041758/skill-cataclysm.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=931ff6d71086308275848429e2aa63b666eb16d6d4d0badb2cba1e0dd5f199a2&"
SKILL_DRAUGHT = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398710949482608/skill-draught.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=e8b12dc767022c53db6d4d2fe6f3e0402274290a1fd69828250710ac336252d3&"
SKILL_ONSLAUGHT = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398711352397946/skill-onslaught.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=eb7e4fb15c4955c26dd597ea8a6daeb2c2470b55701ff148f2e303bdb7094819&"
SKILL_SIPHON = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398711671034006/skill-siphon.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=b801accd130ff5b1f82774b22859711c57299fb80efea054a497b66436a5995a&"
SKILL_SURGE = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398712014835832/skill-surge.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=ce6db5ce0d4fa038d6258a8d167dab19f7dbd2ccd39d3d7767bbde53a7251e9b&"
SKILL_WARDFORGE = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398712359030844/skill-wardforge.jpg?ex=6a0e1ea0&is=6a0ccd20&hm=9bbab6d1affdd7a86c770dcf66846e9b62868a401b4544141bf4bb8aefdd5af7&"

SKILL_IMAGES = {
    "acrimony": SKILL_ACRIMONY,
    "bastion": SKILL_BASTION,
    "cataclysm": SKILL_CATACLYSM,
    "draught": SKILL_DRAUGHT,
    "onslaught": SKILL_ONSLAUGHT,
    "siphon": SKILL_SIPHON,
    "surge": SKILL_SURGE,
    "wardforge": SKILL_WARDFORGE,
}

# ── GENERAL UI ────────────────────────────────────────────────────────────────
CHECKIN = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523698876354560/tavern_checkin.jpg?ex=6a12365a&is=6a10e4da&hm=5561deb1fefbb398f0e5fa7abb9b057ca512d4dab922b8f5d88ce01ea8ce184d&"
PASSIVES = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523697915854940/passive_allocation.jpg?ex=6a12365a&is=6a10e4da&hm=6e234b388ab93754e011c6d305017b6099c0cc8a2c54cf223daba83078f21cba&"
PROPAGATE = "https://cdn.discordapp.com/attachments/1334637411363323996/1506398700421775451/propagate.jpg?ex=6a0e1e9d&is=6a0ccd1d&hm=651f437341cdcc8b45388221cc0cdba0d8061c826ae05290a8d363141e4589d5&"
BLUEPRINT_RESEARCH = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523706438815774/unidentified_blueprint.jpg?ex=6a12365c&is=6a10e4dc&hm=59a1568cc8bfb93031843a03501d9fb0423971aeb2ab07f5c0919bfadf629f07&"
IDEOLOGY_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523697227989002/IDEOLOGY_HUB.jpg?ex=6a123659&is=6a10e4d9&hm=6163cba2902cadda5c9186834d55031e51efbf2849d39e379a5783f52f4c5dfa&"
GUILD_UNREGISTER = "https://cdn.discordapp.com/attachments/1334637411363323996/1507523689296564254/GUILD_UNREGISTER.jpg?ex=6a123657&is=6a10e4d7&hm=e18ca0fd37f1417f02e52e30cc4591a7e8d4e07bde30c2d73412596b7d33146e&"

# ── TAVERN / GENERAL UI ───────────────────────────────────────────────────────
TAVERN_KEEPER = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512945447374948/tavern_keeper.jpeg?ex=69f8b514&is=69f76394&hm=f4a3a9fe2ccef135bce7489b28a7b4f3e5afea70c81df77cac7b297d6ab6dd81&"  # also used as help embed logo
TAVERN_GAMES = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512945850024048/tavern_games.jpeg?ex=69f8b514&is=69f76394&hm=6b14a97a92706c0fb8aa4301a4b793d6cf9f4e01810d572721fdba269c33cb9a&"
BAR_MAID = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512946206281738/tavern_roulette.jpeg?ex=69f8b514&is=69f76394&hm=88200c170f94e9f47dc070f2f1b6a9ca67b4aa660170c072c6b7f4580ea73f7d&"
TAVERN_CASINO = "https://cdn.discordapp.com/attachments/1334637411363323996/1517684190928310372/tavern_casino.jpg?ex=6a372d0c&is=6a35db8c&hm=5774e397605ae025ec3676b5bb2d823b5a89363fc444966c752f47e7c66e2cd8&"  # also used in minigames
DEFAULT_SILHOUETTE = "https://cdn.discordapp.com/attachments/1334637411363323996/1500512946823102566/default_silhouette.jpeg?ex=69f8b514&is=69f76394&hm=31db3a8a07afdcf6563ade9036515d2a727003c11801dd76e6192d75cd19583a&"  # guild/character fallback

# ── ARTISAN MASTERY ───────────────────────────────────────────────────────────
ARTISAN_MASTERY_HUB = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612091655327875/artisan_mastery_hub.jpg?ex=6a19cf51&is=6a187dd1&hm=0f7c82e6fa80506606fb659dfe1a178ab2bfee2cca3a00855c2dc82a4a9e2137&"
ARTISAN_MASTERY_ATTUNEMENT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612091412320534/artisan_mastery_attunement.jpg?ex=6a19cf51&is=6a187dd1&hm=3e650c77bfbbbe7cb45e9d768fe9f38ecf3b33239d85467ac127dfeb3dfb857c&"
MASTERY_MINING = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612113365045529/mastery_mining.jpg?ex=6a19cf57&is=6a187dd7&hm=20f2a245794a1a4b65f444a09ff8c8cc0743fe7cd9a9c74fa8b6a2741548d71f&"
MASTERY_FISHING = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612113109323856/mastery_fishing.jpg?ex=6a19cf57&is=6a187dd7&hm=53324220d5025de53987afb06a84a4e2ffd4d1d9be998e995bde28e1c3130ed5&"
MASTERY_WOODCUTTING = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612112861987067/master_woodcutting.jpg?ex=6a19cf56&is=6a187dd6&hm=75c3a5473e3e56c34cc6801d632f3ba6a67c2bd741bdf92e848cfb2a1fc5e113&"

# ── PRESTIGE GATHERING BOSSES ────────────────────────────────────────────────
# Fight = used in normal combat encounter
# Defeat = used in PrestigeBossHarvestView ("Gather Remnants")
MERIDIAN_GOLEM_FIGHT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612121774624768/meridian_golem_fight.jpg?ex=6a19cf59&is=6a187dd9&hm=6c2e8a735a0e453edc66d30e39d8322a69f6af0e96314a0e34588d61ee40b998&"
MERIDIAN_GOLEM_DEFEAT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612113650384926/meridian_golem_defeat.jpg?ex=6a19cf57&is=6a187dd7&hm=43f2285eff97bfb9b9cb8eec2bb749d2d772ab754b4d179da85fc5a14cce48e0&"

DROWNED_LEVIATHAN_FIGHT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612093207351407/drowned_leviathan_fight.jpg?ex=6a19cf52&is=6a187dd2&hm=9fb8f1685ad6127708638df003ac1854ef91ec31da7aa0f20d8f07da7546474d&"
DROWNED_LEVIATHAN_DEFEAT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612092955689150/drowned_leviathan_defeat.jpg?ex=6a19cf52&is=6a187dd2&hm=93ac6b551e68f7d6d043978af890463332049e1cab2b0d715b0b0e69256b2fee&"

VERDANT_COLOSSUS_FIGHT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612132952445170/verdant_colossus_fight.jpg?ex=6a19cf5b&is=6a187ddb&hm=495b55c976006ef83661f85d2081f3d3dae036e775e7c4a79a7ba519866de7a0&"
VERDANT_COLOSSUS_DEFEAT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612132621357276/verdant_colossus_defeat.jpg?ex=6a19cf5b&is=6a187ddb&hm=a860dfc1d3efddfd271802111d7d06ff385db583c44552836935fee02de4a094&"

# ── APEX MONSTERS ─────────────────────────────────────────────────────────────
APEX_CINDERBORN_DRAKE = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612092377010176/cinderborn_drake.jpg?ex=6a19cf52&is=6a187dd2&hm=a17a6f1a7cd27f745cef66cbb9054646ac708afa07ba5b62d4a8fd92ba11a7b0&"
APEX_EMBER_TYRANT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612093492559942/ember_tyrant.jpg?ex=6a19cf52&is=6a187dd2&hm=0aa906d764a9eac67694201a210d0fcbe688836ec9eacfcdf7a025c7551ef88c&"
APEX_ASHFALL_COLOSSUS = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612091886272552/ashfall_colossus.jpg?ex=6a19cf51&is=6a187dd1&hm=08b87c249240bba325937eb909c72fc0c7ef16d3248f71c6f044b467e7b7eb58&"
APEX_MAGMA_HYDRA = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612112585167022/magma_hydra.jpg?ex=6a19cf56&is=6a187dd6&hm=5e47fad8707f145b01efedde70c4d15deebd6b3d45a763552ef1c1e16bd2c565&"
APEX_PYROCLAST_SPECTER = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612122265620582/pyroclast_specter.jpg?ex=6a19cf59&is=6a187dd9&hm=8718169eb35f17c5f771c5cb2cac7692277b6cad7db5d2b1a98e7f2b955ce988&"

APEX_STORMCALLER_WYRM = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612123767046184/stormcaller_wyrm.jpg?ex=6a19cf59&is=6a187dd9&hm=95c3cfddc10f3a9d83f7eecef3c965613f0bb77cc745cde74d255fc89ff7f1ac&"
APEX_TEMPEST_SOVEREIGN = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612124039548950/tempest_sovereign.jpg?ex=6a19cf59&is=6a187dd9&hm=37de68ec25b2dfe68d411d89797731d7d84290383c053786a6471697fb8a5e80&"
APEX_CYCLONE_REVENANT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612092611887295/cyclone_revenant.jpg?ex=6a19cf52&is=6a187dd2&hm=a9dc8518d64c1723ae48c1e5d266888c2373966eec05ef40a9f8476fb0efd771&"
APEX_THUNDER_BEHEMOTH = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612131849601277/thunder_behemoth.jpg?ex=6a19cf5b&is=6a187ddb&hm=c932bdacc0b3790f6e1a9f179b32c9d10a9bea2107ffbb4d19b83170ef3d3025&"
APEX_VOLTAIC_SHADE = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612133732843570/voltaic_shade.jpg?ex=6a19cf5b&is=6a187ddb&hm=0ead831e70cbadb659c71270fedc84af46cf6f9594cfe4303467f2f7b660dc22&"

APEX_SIEGE_MASTER = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612123523780800/siege_master.jpg?ex=6a19cf59&is=6a187dd9&hm=006b7fb03fa570ba05ab83ed22b536d71a6071bde465737539e249d8c0e86d87&"
APEX_IRON_GOLEM_LORD = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612103726661732/iron_golem_lord.jpg?ex=6a19cf54&is=6a187dd4&hm=356fba25d5dfa3756d95d9771534a0a409466d46795764fc396b9321196d70d8&"
APEX_WARDEN_OF_IRON = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612133959209200/warden_of_iron.jpg?ex=6a19cf5b&is=6a187ddb&hm=251b65c9a0096b3befcbcf3db0b68ad142021c87c77c34ee8dc80904d28a8c71&"
APEX_FORTRESS_COLOSSUS = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612102418039076/fortress_colossus.jpg?ex=6a19cf54&is=6a187dd4&hm=e568df5419f54627364df4da12bbbf7e132d16b7863128ca62831d00091f268b&"
APEX_BASTION_WRAITH = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612092133605640/bastion_wraith.jpg?ex=6a19cf52&is=6a187dd2&hm=8a1b9fa5758506904d4ca3e56401aefdadc899f078639bf42cfb92491e8f607f&"

APEX_GROVE_ANCIENT = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612103474876546/grove_ancient.jpg?ex=6a19cf54&is=6a187dd4&hm=c7d0f11f7c755a2ed0fefcd562f176cadcd9bc35856b87881a40137b131b8c87&"
APEX_THORNWEALD_TITAN = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612124307984577/thornweald_titan.jpg?ex=6a19cf59&is=6a187dd9&hm=c7a485c13da28f5001fff6885f8638a2771261961e19f7b462a1c176936e6ff7&"
APEX_VERDANT_DEVOURER = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612133233594398/verdant_devourer.jpg?ex=6a19cf5b&is=6a187ddb&hm=8d29d0df53f5fb6b942a74c6083e6c1eb1457d8fa3d13eebea31b08c10608297&"
APEX_LIVING_CANOPY = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612112295624885/living_canopy.jpg?ex=6a19cf56&is=6a187dd6&hm=63503bd1daa5f2c15498a33fdddae67ddca3a198f6784ecfdfd4de95a12ca388&"
APEX_ROOT_SOVEREIGN = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612123251147053/root_sovereign.jpg?ex=6a19cf59&is=6a187dd9&hm=92f861e5c2597f2ada332ef788f2e1cdb5cdbcb4bd912c5feb4a7e22b13c0429&"

APEX_VAULT_SENTINEL = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612123523780800/siege_master.jpg?ex=6a19cf59&is=6a187dd9&hm=006b7fb03fa570ba05ab83ed22b536d71a6071bde465737539e249d8c0e86d87&"
APEX_GILDED_PREDATOR = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612102984273980/gilded_predator.jpg?ex=6a19cf54&is=6a187dd4&hm=d233ad106d529fd00972b489f6d712a1b3fbff1421b9cd5ebaf71e99d5d21e0b&"
APEX_FORTUNES_REAPER = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612102644666609/fortunes_reaper.jpg?ex=6a19cf54&is=6a187dd4&hm=a65a05e6108c2d2883b568c77d44a1112390448db07397ce86dd29905e6f6f6b&"
APEX_GREED_INCARNATE = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612103210897710/greed_incarnate.jpg?ex=6a19cf54&is=6a187dd4&hm=04c42b6db7d5ec14753843c51063bcb0830b45dd1b1a7611a5fee19ce9f6678e&"
APEX_VAULT_PHANTOM = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612132075835553/vault_phantom.jpg?ex=6a19cf5b&is=6a187ddb&hm=af61a1cea7aedce67a090c367b8feddae64d39c21f4bf624073f4839c2f98adf&"

APEX_REALITY_SHREDDER = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612122534051850/reality_shredder.jpg?ex=6a19cf59&is=6a187dd9&hm=c11a0cca6dc8d3330ac734dd36621f04cb88b6f30f949fdc7367cc85cb4df625&"
APEX_VOID_FRACTURE = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612133472800778/void_fracture.jpg?ex=6a19cf5b&is=6a187ddb&hm=f88999bd0087e91e1943c3f429e35a7fcdd541a234504a9238c59b2392fce86c&"
APEX_ENTROPY_ENGINE = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612103726661732/iron_golem_lord.jpg?ex=6a19cf54&is=6a187dd4&hm=356fba25d5dfa3756d95d9771534a0a409466d46795764fc396b9321196d70d8&"
APEX_NEXUS_ABOMINATION = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612122026283258/nexus_abomination.jpg?ex=6a19cf59&is=6a187dd9&hm=e7075d92b22650c3a8b05a55a94a5c56bbcb1ded4d405ea2546891d717e27e24&"
APEX_RIFT_LEVIATHAN = "https://cdn.discordapp.com/attachments/1334637411363323996/1509612122735120434/rift_leviathan.jpg?ex=6a19cf59&is=6a187dd9&hm=053b56c2498cc3873dc79861d2d7f7df005cfb5552dfa566eac6ef379c03c72e&"

# ── NETHER MARKET ──────────────────────────────────────────────────────────
VEX_PORTRAIT = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970542851133460/vex_profile.jpg?ex=6a46c506&is=6a457386&hm=55beb84cdd195a26304e4f82320d30e4fb19a12a82b29b1eb9de52ca6057cc5b&"
VEX_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970543086272613/vex_thumbnail.jpg?ex=6a46c506&is=6a457386&hm=ff17d623f1882fb2b065ec971ef56092412ce57ae728e8d511efb780ad780052&"
NETHER_NPC_PENNY_LOAFER_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970542486225008/penny_loafer.jpg?ex=6a46c506&is=6a457386&hm=7caa5e4cd429a2b35b139a4f548f8658cefc5e538a4e5abab9eadc8f21a20c69&"
NETHER_NPC_OLD_OTTO_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970542272577667/old_otto.jpg?ex=6a46c506&is=6a457386&hm=3fe3dab377854548139722d7be77017c397f56c9d60f9da1f1d1822e7a7fe1e0&"
NETHER_NPC_LADY_FENWICK_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970541999689818/lady_fenwick.jpg?ex=6a46c506&is=6a457386&hm=d4eedb41df0ed79cb4aa51c720c8f721075f1bc8f20c407b19d032953845cd8d&"
NETHER_NPC_IRONMONGER_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970541785911366/ironmonger.jpg?ex=6a46c506&is=6a457386&hm=53836ee6838e694938e5a045f2175d5b01b471d7d32b9de12b86be66d0e5d245&"
NETHER_NPC_COUNTESS_VAELORA_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970541261623418/countess_vael.jpg?ex=6a46c505&is=6a457385&hm=0c1795051ce727338745f048c29af1d925e8f774d54ed713dfa7e2a3b1be0212&"
NETHER_NPC_THE_HOARDER_THUMBNAIL = "https://cdn.discordapp.com/attachments/1334637411363323996/1521970541529927791/hoarder.jpg?ex=6a46c505&is=6a457385&hm=2801dad317700dda1301488e10f7d52d71658fe88bdd0538fa947a40d3f4b5a1&"

# ── INNER SANCTUM ──────────────────────────────────────────────────────────
# TODO: source real art and replace with a hosted CDN URL (see scripts/upload_new.py).
# Left as None so embed.set_thumbnail(url=None) simply omits the thumbnail.
INNER_SANCTUM_THUMBNAIL = None

# ── PRESTIGE AVATARS ──────────────────────────────────────────────────────────
# Purchasable animated avatar gallery (cogs/prestige.py). Keys are internal
# codenames; display labels + tier pricing live in cogs/prestige.py:
# PRESTIGE_AVATAR_CATALOG.
PRESTIGE_AVATARS_MALE = {
    "berserker": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246978920452136/male_berserker-1.gif?ex=6a4f0d1e&is=6a4dbb9e&hm=8a64158e4f1628f60dc8f931d8592896fa5ec391a9d29adf3da2e1d5a7a0286b&",
    "gilded": "https://cdn.discordapp.com/attachments/1334637411363323996/1524849628640710676/gilded_sov.gif?ex=6a513e61&is=6a4fece1&hm=267531452767f5eae769669d9f693c6da35be6330d16d60cbf4052837eb74e93&",
    "ronin": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246980019359814/male_ronin-1.gif?ex=6a4f0d1f&is=6a4dbb9f&hm=9492ca69176d60f02af3a7537cc56d57a24243c4d08da2346ddbbf836543e6ca&",
    "wiz": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246988152115300/male_wiz-1.gif?ex=6a4f0d21&is=6a4dbba1&hm=2418293c155b20e6fa6cd1febbd3819d4b9dee42963e352f006bb466cabcf90a&",
}

PRESTIGE_AVATARS_FEMALE = {
    "bloodmage": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246935933030450/female_bloodmage-1.gif?ex=6a4f0d14&is=6a4dbb94&hm=789b6eb7c2de39355adab4427bd8b5bde9c55910622d9c98b25c5b1f17e22a7f&",
    "gem": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246936474091520/female_gem-1.gif?ex=6a4f0d14&is=6a4dbb94&hm=c05b27742306f79103051b748faa5bd1b56c825b64cdf19fb99efede1e9e935f&",
    "hunt": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246936927080538/female_hunt-1.gif?ex=6a4f0d14&is=6a4dbb94&hm=3beffff2bbef5fbba68503834ebf15abecded4519baf4f1eaaa4e706e8a7f24a&",
    "ninja": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246945554632764/female_ninja-1.gif?ex=6a4f0d16&is=6a4dbb96&hm=ade3963467d912d6d8202d2e61fe4654c1c38ff3d30117c2f0c7a336641a0b8e&",
    "sorc": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246946045231205/female_sorc-1.gif?ex=6a4f0d17&is=6a4dbb97&hm=33c590d13b89e8df3f252dff088918b1b53f11e3ba2690582415c2cd5cf16810&",
    "void": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246968837210182/female_void-1.gif?ex=6a4f0d1c&is=6a4dbb9c&hm=57a08357e84551fd742193fb609b759da2d5a0c548c16e9a337cbd56fe921ceb&",
    "warriorangel": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246978341634048/female_warriorangel-1.gif?ex=6a4f0d1e&is=6a4dbb9e&hm=b15e25efc6acc71b957834d898adf10c9aca2c83e262876d3e7b75d4e668e3f7&",
}

PRESTIGE_AVATARS_FEMALE_SS = {
    "bride": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246946519318569/female_ss_bride.gif?ex=6a4f0d17&is=6a4dbb97&hm=68f20caa59b83c73d604f8eabef3143d5b2487c7db890b88e951c110dc52e58c&",
    "deepocean": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246947047673977/female_ss_deepocean.gif?ex=6a4f0d17&is=6a4dbb97&hm=43692a1c367320387ba8a195172f5e68b2657cca90015c890e3b04d81b92fdc6&",
    "fox": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246956032000090/female_ss_fox.gif?ex=6a4f0d19&is=6a4dbb99&hm=39a28316056c278a4aead7de083a7ee4d7d326cf9f07aea6f6160451290a2471&",
    "ice": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246956690509844/female_ss_ice.gif?ex=6a4f0d19&is=6a4dbb99&hm=2e5a42af4a6d24dd091074565d6b4bf9507abee4577b876b7045a51ef4f16c2e&",
    "oni": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246957273514154/female_ss_oni.gif?ex=6a4f0d19&is=6a4dbb99&hm=5359004fc68befb7d34ef2db1ea0a4c6776a4fb7f441a38e9f77fa0c7b68c05d&",
    "petals": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246957818777620/female_ss_petals.gif?ex=6a4f0d19&is=6a4dbb99&hm=14ae4cb9464fd2d0c6b2801378674e866c20984a62823835f490bfea6de560e0&",
    "snow": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246967377727628/female_ss_snow.gif?ex=6a4f0d1c&is=6a4dbb9c&hm=e13832b3843f365b0ce63d5c782ccd63d4773db5dc40cc7ab94b88bb4c5146cc&",
    "storm": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246967860068382/female_ss_storm.gif?ex=6a4f0d1c&is=6a4dbb9c&hm=1966b55a6e691dd3ff333c154efb141689254422f9b9284f93fb5606961073fc&",
    "tech": "https://cdn.discordapp.com/attachments/1334637411363323996/1524246968359063573/female_ss_tech.gif?ex=6a4f0d1c&is=6a4dbb9c&hm=719c1a4c56359816b3ea58d43db82486e05450959963c3e6d53adce358bf78db&",
    "angel": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248367154696286/female_ss_angel.gif?ex=6a52b1bc&is=6a51603c&hm=fcac6738e221309223d4922d30aa795bcec6c1b7890c32776d9ae9ae9f93ff67&",
    "fire": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248374914416800/female_ss_fire.gif?ex=6a52b1be&is=6a51603e&hm=bb3f5b376727a0fce14a6662240cb96604a5b7b83bd5bc4ea842c49a24281e9b&",
    "rose": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248384179507330/female_ss_rose.gif?ex=6a52b1c0&is=6a516040&hm=748c10bddd7effca78f9a2bbbc5e4e3676ba68196f1ffa77f74b0661c4c03fcf&",
    "thunder": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248391813009458/female_ss_thunder.gif?ex=6a52b1c2&is=6a516042&hm=0649f5c83d5aba729dc8423ff95e2def41cd413383bec31285130daff1fee649&",
    "void": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248399551762543/female_ss_void.gif?ex=6a52b1c4&is=6a516044&hm=e941965d8bcc29d06bf945bc747a5f0e4140ac2e10e7ac74915313c90a72b880&",
}

PRESTIGE_AVATARS_MALE_SS = {
    "celestial": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248425371898139/male_ss_celestial.gif?ex=6a52b1ca&is=6a51604a&hm=705863a8eb72572412f1025f3199d16adabf4f129ace971a907ac91a83022adb&",
    "cyber_emperor": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248433575956530/male_ss_cyber_emperor.gif?ex=6a52b1cc&is=6a51604c&hm=a4243ed80d01bcafc17798f0458bd2e98bb078e9ddd37f99a378f1a4fa5d3084&",
    "dragon": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248440756600872/male_ss_dragon.gif?ex=6a52b1ce&is=6a51604e&hm=d067b360b7dadcab215ab86fbf502a879edc7c67ff043784001ab2b73792a001&",
    "samurai_lord": "https://cdn.discordapp.com/attachments/1334637411363323996/1525248448574525470/male_ss_samurai_lord.gif?ex=6a52b1cf&is=6a51604f&hm=e82d1936c7eb3126a6e85080559b57e6f9f8895ca58ff37e37a1514392eb06aa&",
}
