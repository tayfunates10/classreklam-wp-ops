#!/usr/bin/env python3
import base64, json, os, re, sys, urllib.error, urllib.parse, urllib.request

BASE = os.environ['WP_URL'].rstrip('/')
USER = os.environ['WP_USER']
APP = os.environ['WP_APP_PASSWORD']
AUTH = 'Basic ' + base64.b64encode(f'{USER}:{APP}'.encode()).decode()


def request(method, path, payload=None):
    url = BASE + path
    data = None
    headers = {'Authorization': AUTH, 'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode('utf-8', errors='replace')
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace')
        try: body = json.loads(raw)
        except Exception: body = {'raw': raw[:1000]}
        return e.code, body


def rank_meta(object_id, title, description, focus, canonical):
    payload = {
        'objectType': 'post',
        'objectID': int(object_id),
        'meta': {
            'rank_math_title': title,
            'rank_math_description': description,
            'rank_math_focus_keyword': focus,
            'rank_math_canonical_url': canonical,
        }
    }
    code, body = request('POST', '/wp-json/rankmath/v1/updateMeta', payload)
    if code not in (200, 201):
        raise RuntimeError(f'Rank Math updateMeta failed for {object_id}: HTTP {code} {body}')
    return code


def wp_blocks(intro, sections, faq):
    out = []
    out += ['<!-- wp:paragraph -->', f'<p>{intro}</p>', '<!-- /wp:paragraph -->']
    for heading, paragraphs, bullets in sections:
        out += ['<!-- wp:heading -->', f'<h2 class="wp-block-heading">{heading}</h2>', '<!-- /wp:heading -->']
        for p in paragraphs:
            out += ['<!-- wp:paragraph -->', f'<p>{p}</p>', '<!-- /wp:paragraph -->']
        if bullets:
            out += ['<!-- wp:list -->', '<ul class="wp-block-list">']
            out += [f'<li>{x}</li>' for x in bullets]
            out += ['</ul>', '<!-- /wp:list -->']
    out += ['<!-- wp:heading -->', '<h2 class="wp-block-heading">Sık Sorulan Sorular</h2>', '<!-- /wp:heading -->']
    for q, a in faq:
        out += ['<!-- wp:heading {"level":3} -->', f'<h3 class="wp-block-heading">{q}</h3>', '<!-- /wp:heading -->']
        out += ['<!-- wp:paragraph -->', f'<p>{a}</p>', '<!-- /wp:paragraph -->']
    out += [
        '<!-- wp:separator -->', '<hr class="wp-block-separator has-alpha-channel-opacity"/>', '<!-- /wp:separator -->',
        '<!-- wp:heading -->', '<h2 class="wp-block-heading">Projeniz İçin Teklif Alın</h2>', '<!-- /wp:heading -->',
        '<!-- wp:paragraph -->', '<p>Ölçü, uygulama alanı ve istediğiniz görünümü paylaşın; projenize uygun üretim ve uygulama seçeneğini birlikte netleştirelim.</p>', '<!-- /wp:paragraph -->',
        '<!-- wp:buttons -->', '<div class="wp-block-buttons">',
        '<!-- wp:button -->', '<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="tel:+905469364271">0546 936 42 71</a></div>', '<!-- /wp:button -->',
        '<!-- wp:button {"className":"is-style-outline"} -->', '<div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="https://wa.me/905469364271">WhatsApp ile Teklif Al</a></div>', '<!-- /wp:button -->',
        '</div>', '<!-- /wp:buttons -->',
        '<!-- wp:paragraph -->', '<p><strong>Class Reklam</strong> — Edremit / Balıkesir</p>', '<!-- /wp:paragraph -->'
    ]
    return '\n'.join(out)


SERVICES = [
    {
        'slug':'edremit-tabela', 'title':'Edremit Tabela',
        'seo_title':'Edremit Tabela | Işıklı ve Işıksız Tabela | Class Reklam',
        'description':'Edremit tabela çözümleri: ışıklı ve ışıksız tabela, cephe tabelası, yönlendirme ve özel üretim. Class Reklam’dan keşif ve teklif alın.',
        'focus':'edremit tabela',
        'intro':'Edremit’te işletmenizin cephede, sokakta ve uzaktan daha kolay fark edilmesi için kullanım alanına uygun tabela çözümleri üretiyoruz. Tasarım, malzeme seçimi, üretim ve montaj adımlarını işletmenizin konumuna ve görünürlük ihtiyacına göre planlıyoruz.',
        'sections':[
            ('Edremit’te Tabela Çözümleri', ['Tabela yalnızca işletme adını gösteren bir pano değildir; okunabilirlik, gece-gündüz görünürlük ve marka bütünlüğü birlikte ele alınmalıdır. Class Reklam; mağaza, ofis, fabrika ve hizmet noktaları için farklı tabela tipleri uygular.'], ['Işıklı ve ışıksız cephe tabelaları','Kutu harf ve logo uygulamaları','Totem ve yönlendirme tabelaları','Kompozit zemin ve cephe üstü uygulamalar']),
            ('Doğru Tabela Nasıl Planlanır?', ['Cephe ölçüsü, görüş mesafesi, montaj yüzeyi ve çevresel koşullar tasarım kararlarını doğrudan etkiler. Önce uygulama alanını ve kullanım amacını netleştirir, ardından malzeme ve aydınlatma seçeneğini belirleriz.'], ['Okunabilir harf yüksekliği ve kontrast','Dış mekâna uygun malzeme seçimi','Kablo ve aydınlatma detaylarının düzenli çözülmesi','Montaj noktasına uygun taşıyıcı sistem']),
            ('Edremit ve Balıkesir Çevresinde Uygulama', ['Edremit merkezli çalışarak yakın çevrede tabela, baskı, folyo ve giydirme projelerine hizmet veriyoruz. Uygulama öncesi ölçü ve görseller üzerinden kapsamı netleştirmek teklif sürecini hızlandırır.'], [])
        ],
        'faq':[
            ('Tabela fiyatı neye göre değişir?', 'Ölçü, malzeme, ışıklandırma, harf tipi, taşıyıcı sistem ve montaj koşulları fiyatı belirleyen temel unsurlardır.'),
            ('Işıklı mı ışıksız tabela mı tercih edilmeli?', 'Akşam görünürlüğünün önemli olduğu noktalarda ışıklı çözümler avantaj sağlar. Gündüz kullanımının baskın olduğu veya aydınlatmanın farklı çözüldüğü cephelerde ışıksız seçenekler uygun olabilir.'),
            ('Ölçü almadan teklif alınabilir mi?', 'Yaklaşık ölçü ve cephe fotoğrafı ile ön değerlendirme yapılabilir; kesin üretim için uygulama ölçülerinin doğrulanması gerekir.')]
    },
    {
        'slug':'totem-tabela', 'title':'Totem Tabela',
        'seo_title':'Edremit Totem Tabela | Yol Kenarı Totem | Class Reklam',
        'description':'Edremit totem tabela üretimi ve uygulaması. Yol kenarı, işletme girişi ve geniş alanlarda görünürlüğü artıran kurumsal totem çözümleri.',
        'focus':'edremit totem tabela',
        'intro':'Totem tabela, özellikle yoldan geçen araç ve yayaların işletmenizi uzaktan fark etmesini sağlayan güçlü bir dış mekân reklam çözümüdür. Edremit ve çevresinde konuma, görüş mesafesine ve kurumsal kimliğe uygun totem tabela projeleri hazırlıyoruz.',
        'sections':[
            ('Totem Tabela Nerelerde Kullanılır?', ['Totemler çoğunlukla yol kenarında, fabrika ve site girişlerinde, akaryakıt ve hizmet noktalarında, mağaza önlerinde ve geniş açık alanlarda kullanılır.'], ['İşletme ve mağaza girişleri','Fabrika ve üretim tesisi girişleri','Yol kenarı yönlendirme ve marka görünürlüğü','Birden fazla işletmenin bulunduğu ticari alanlar']),
            ('Tasarım ve Üretimde Dikkat Edilenler', ['Yükseklik tek başına yeterli değildir. Logo oranı, yazı boyutu, kontrast, ışıklandırma ve taşıyıcı gövde bir bütün olarak planlanmalıdır. Dış mekân koşullarına uygun yüzey ve bağlantı detayları tercih edilir.'], []),
            ('Işıklı Totem Seçeneği', ['Gece görünürlüğü gereken projelerde LED aydınlatmalı yüzeyler veya ışıklı kutu harf çözümleri kullanılabilir. Aydınlatma biçimi tasarım ve konuma göre belirlenir.'], [])
        ],
        'faq':[
            ('Totem tabela yüksekliği nasıl belirlenir?', 'Görüş mesafesi, yol kotu, çevredeki engeller, cephe ve uygulama alanı birlikte değerlendirilerek ölçü belirlenir.'),
            ('Totem tabela ışıklı yapılabilir mi?', 'Evet. Projeye göre içten aydınlatma, ışıklı logo veya kutu harf seçenekleri uygulanabilir.'),
            ('Mevcut totemin yüzeyi yenilenebilir mi?', 'Taşıyıcı gövdenin durumu uygunsa yüzey, görsel veya aydınlatma bileşenleri proje bazında yenilenebilir.')]
    },
    {
        'slug':'dijital-baski', 'title':'Dijital Baskı',
        'seo_title':'Edremit Dijital Baskı | Vinil, Branda ve Folyo | Class Reklam',
        'description':'Edremit dijital baskı hizmetleri: vinil, branda, folyo ve dış mekân baskı uygulamaları. Ölçünüze ve kullanım alanınıza uygun üretim.',
        'focus':'edremit dijital baskı',
        'intro':'İç ve dış mekân reklam uygulamalarında doğru baskı malzemesi, renklerin görünümü kadar kullanım ömrünü de etkiler. Edremit’te vinil, branda, folyo ve farklı yüzeylere uygun dijital baskı çözümleri sunuyoruz.',
        'sections':[
            ('Dijital Baskı Uygulama Alanları', ['Kampanya görsellerinden cephe reklamlarına, mağaza camlarından yönlendirme grafiklerine kadar farklı ölçülerde baskılar hazırlanabilir.'], ['Vinil ve folyo baskı','Branda ve dış mekân görselleri','Vitrin ve cam grafik uygulamaları','Tabela yüzeyi ve pano grafikleri']),
            ('İç Mekân ve Dış Mekân Farkı', ['Güneş, yağmur ve sıcaklık değişimleri dış mekân baskılarında malzeme ve mürekkep seçimlerini daha kritik hale getirir. Uygulama yüzeyine göre laminasyon veya koruyucu çözümler değerlendirilebilir.'], []),
            ('Dosya ve Ölçü Hazırlığı', ['Net sonuç için tasarımın gerçek baskı ölçüsüne uygun hazırlanması, düşük çözünürlüklü görsellerden kaçınılması ve kesim paylarının doğru tanımlanması önemlidir.'], [])
        ],
        'faq':[
            ('Dijital baskıda hangi dosya formatları uygundur?', 'Vektörel PDF, AI veya yüksek çözünürlüklü görseller işin türüne göre tercih edilir. Mevcut dosyanızı kontrol ederek uygunluğu belirleyebiliriz.'),
            ('Dış mekân baskısı ne kadar dayanır?', 'Dayanım; malzeme, baskı türü, güneş maruziyeti, yüzey ve bakım koşullarına göre değişir.'),
            ('Baskı sonrası uygulama da yapıyor musunuz?', 'Projenin kapsamına göre baskı ile birlikte folyo, cam, pano veya cephe uygulaması planlanabilir.')]
    },
    {
        'slug':'arac-giydirme', 'title':'Araç Giydirme',
        'seo_title':'Edremit Araç Giydirme ve Araç Kaplama | Class Reklam',
        'description':'Edremit araç giydirme ve araç kaplama hizmeti. Ticari araçlar için kurumsal folyo, baskılı grafik ve mobil reklam uygulamaları.',
        'focus':'edremit araç giydirme',
        'intro':'Araç giydirme, ticari aracınızı hareketli bir reklam alanına dönüştürür. Edremit’te firma logosu, iletişim bilgileri, kurumsal grafikler ve kampanya görselleri için araç yüzeyine uygun folyo uygulamaları hazırlıyoruz.',
        'sections':[
            ('Araç Giydirme Seçenekleri', ['Marka ihtiyacına göre sade logo ve iletişim uygulamasından geniş yüzeyli baskılı grafiklere kadar farklı kapsamlar planlanabilir.'], ['Kesim folyo logo ve yazı uygulaması','Baskılı folyo ile kısmi giydirme','Ticari araç kasa ve panel uygulamaları','Kurumsal renk ve görsel bütünlüğü']),
            ('Uygulama Öncesi Hazırlık', ['Yüzeyin temiz, kuru ve uygulamaya uygun olması folyonun performansı açısından önemlidir. Kaporta üzerindeki hasar, boya durumu ve kıvrımlı yüzeyler uygulama öncesinde değerlendirilir.'], []),
            ('Tasarımda Okunabilirlik', ['Araç hareket halinde olduğu için mesajın hızlı anlaşılması gerekir. Logo, telefon ve temel hizmet bilgilerini gereksiz kalabalık oluşturmadan görünür yerleştirmek daha etkilidir.'], [])
        ],
        'faq':[
            ('Araç tamamen kaplanmak zorunda mı?', 'Hayır. İhtiyaca göre yalnızca logo-yazı, kısmi grafik veya daha geniş kaplama yapılabilir.'),
            ('Araç giydirme tasarımını hazırlıyor musunuz?', 'Araç ölçüsü, marka materyalleri ve hedeflenen görünüm doğrultusunda uygulamaya uygun tasarım düzenlenebilir.'),
            ('Uygulama öncesi araç nasıl hazırlanmalı?', 'Araç yüzeyi temiz olmalı; yoğun cila, silikon, yağ ve kir kalıntıları uygulamayı olumsuz etkileyebileceği için yüzey hazırlığı önemlidir.')]
    },
    {
        'slug':'cam-giydirme', 'title':'Cam Giydirme',
        'seo_title':'Edremit Cam Giydirme | One Way Vision ve Folyo | Class Reklam',
        'description':'Edremit cam giydirme ve vitrin folyo uygulamaları. One way vision, buzlu folyo, kesim folyo ve reklam amaçlı cam kaplama çözümleri.',
        'focus':'edremit cam giydirme',
        'intro':'Mağaza ve ofis camları hem reklam hem de mekân algısı için değerli yüzeylerdir. Edremit’te vitrin, kapı ve cam cephelerde reklam, yönlendirme, dekorasyon ve mahremiyet amaçlı folyo uygulamaları yapıyoruz.',
        'sections':[
            ('Cam Folyo Çeşitleri', ['İhtiyaca göre dışarıdan reklam görünürlüğü, içeride mahremiyet veya sade dekoratif görünüm hedeflenebilir.'], ['One way vision baskılı cam uygulaması','Buzlu / kumlama görünümlü folyo','Kesim folyo yazı ve logo','Tam veya kısmi vitrin giydirme']),
            ('Vitrin Tasarımında Denge', ['Cam yüzeyin tamamını kapatmak her proje için doğru olmayabilir. İçerinin görünmesi gereken alanlar, giriş kapıları ve görüş seviyeleri dikkate alınarak grafik yoğunluğu planlanır.'], []),
            ('Uygulama Yüzeyi', ['Folyonun düzgün görünmesi için camın yağ, silikon ve yoğun kirden arındırılmış olması gerekir. Ek yerleri ve kesimler mümkün olduğunca tasarıma göre planlanır.'], [])
        ],
        'faq':[
            ('One way vision içeriden görüşü tamamen kapatır mı?', 'Perfore yapısı sayesinde uygun ışık koşullarında içeriden dışarı görüşe yardımcı olur; görünüm ortam ışığı ve baskı yoğunluğuna göre değişebilir.'),
            ('Buzlu folyo nerelerde kullanılır?', 'Ofis bölmeleri, klinikler, toplantı alanları ve mahremiyet istenen cam yüzeylerde sık tercih edilir.'),
            ('Eski folyo sökülüp yenisi uygulanabilir mi?', 'Cam ve mevcut yapışkanın durumuna göre eski folyo sökülerek yüzey temizliği sonrası yeni uygulama yapılabilir.')]
    },
    {
        'slug':'kutu-harf-tabela', 'title':'Kutu Harf Tabela',
        'seo_title':'Edremit Kutu Harf Tabela | Işıklı Kutu Harf | Class Reklam',
        'description':'Edremit kutu harf tabela çözümleri. Işıklı ve ışıksız kutu harf, logo ve cephe uygulamaları için Class Reklam’dan teklif alın.',
        'focus':'edremit kutu harf tabela',
        'intro':'Kutu harf tabela, logoyu ve marka adını cephede üç boyutlu ve güçlü bir görünümle öne çıkarır. Edremit’te mağaza, ofis ve işletme cepheleri için ışıklı veya ışıksız kutu harf uygulamaları hazırlıyoruz.',
        'sections':[
            ('Kutu Harf Seçenekleri', ['Malzeme, yüzey ve aydınlatma biçimi marka kimliğine ve montaj alanına göre seçilir.'], ['Pleksi yüzeyli ışıklı kutu harf','Metal görünümlü ışıklı veya ışıksız harf','Logo ve sembol uygulamaları','Zeminli veya doğrudan cephe montajı']),
            ('Işıklı Kutu Harf', ['Gece görünürlüğünü artırmak için LED aydınlatmalı çözümler tercih edilebilir. Işığın homojen görünmesi için harf derinliği, LED yerleşimi ve yüzey malzemesi birlikte planlanır.'], []),
            ('Cepheye Uyum', ['Harf ölçüsü ve renk seçimi, cephe zeminine karşı yeterli kontrast sağlamalıdır. Küçük ölçekte okunabilir görünen bir tasarım, yüksek cephede aynı etkiyi vermeyebilir; görüş mesafesi dikkate alınmalıdır.'], [])
        ],
        'faq':[
            ('Kutu harf ışıklı olmak zorunda mı?', 'Hayır. Marka ve cephe ihtiyacına göre ışıklı veya ışıksız üretilebilir.'),
            ('Kutu harf tabela hangi zeminlere uygulanabilir?', 'Kompozit cephe, duvar, panel ve uygun taşıyıcı yüzeyler dahil farklı zeminlerde montaj yöntemi projeye göre belirlenir.'),
            ('Logo da kutu harf gibi üretilebilir mi?', 'Logonun formu ve üretim tekniğine uygunluğu değerlendirilerek üç boyutlu logo uygulaması yapılabilir.')]
    }
]


def upsert_page(item):
    q = urllib.parse.quote(item['slug'])
    code, found = request('GET', f'/wp-json/wp/v2/pages?slug={q}&context=edit&per_page=10')
    if code != 200:
        raise RuntimeError(f'Page lookup failed {item["slug"]}: {code} {found}')
    content = wp_blocks(item['intro'], item['sections'], item['faq'])
    payload = {'title': item['title'], 'slug': item['slug'], 'status': 'publish', 'content': content}
    if found:
        page_id = found[0]['id']
        code, body = request('POST', f'/wp-json/wp/v2/pages/{page_id}', payload)
    else:
        code, body = request('POST', '/wp-json/wp/v2/pages', payload)
        page_id = body.get('id') if isinstance(body, dict) else None
    if code not in (200, 201) or not page_id:
        raise RuntimeError(f'Page upsert failed {item["slug"]}: {code} {body}')
    canonical = f'{BASE}/{item["slug"]}/'
    rank_meta(page_id, item['seo_title'], item['description'], item['focus'], canonical)
    return {'slug': item['slug'], 'id': page_id, 'http': code, 'canonical': canonical}


def update_homepage(links):
    code, page = request('GET', '/wp-json/wp/v2/pages/6?context=edit')
    if code != 200:
        raise RuntimeError(f'Homepage read failed: {code} {page}')
    raw = page['content']['raw']
    before = raw
    raw, h1a = re.subn(r'<span class="cr-heading-line1">Baskı, Tabela ve Folyo Çözümlerinde</span>', '<span class="cr-heading-line1">Edremit Tabela ve Reklam</span>', raw, count=1)
    raw, h1b = re.subn(r'<span class="cr-heading-line2">Profesyonel Hizmet</span>', '<span class="cr-heading-line2">Çözümleri</span>', raw, count=1)
    if h1a != 1 or h1b != 1:
        raise RuntimeError(f'Homepage H1 safety check failed: {h1a=} {h1b=}')
    names = {
        'Tabela':'edremit-tabela', 'Totem':'totem-tabela', 'Dijital Baskı':'dijital-baski',
        'Araç Giydirme':'arac-giydirme', 'Cam Giydirme':'cam-giydirme', 'Kutu Harf':'kutu-harf-tabela'
    }
    replacements = {}
    for name, slug in names.items():
        pattern = rf'(<article class="cr-service-card">(?:(?!</article>).)*?<h3>{re.escape(name)}</h3>(?:(?!</article>).)*?<a href=")/hizmetlerimiz("[^>]*>Detaylı İncele)'
        raw, n = re.subn(pattern, rf'\1/{slug}/\2', raw, count=1, flags=re.S)
        replacements[name] = n
        if n != 1:
            raise RuntimeError(f'Homepage service link safety check failed for {name}: {n}')
    if raw == before:
        raise RuntimeError('Homepage unchanged unexpectedly')
    code, body = request('POST', '/wp-json/wp/v2/pages/6', {'content': raw})
    if code not in (200, 201):
        raise RuntimeError(f'Homepage update failed: {code} {body}')
    rank_meta(
        6,
        'Edremit Tabela ve Reklam | Class Reklam',
        'Edremit’te tabela, totem, kutu harf, dijital baskı, araç ve cam giydirme çözümleri. Class Reklam’dan keşif ve teklif alın.',
        'edremit tabela',
        BASE + '/'
    )
    return {'http': code, 'h1_replacements': [h1a, h1b], 'service_link_replacements': replacements}


def main():
    results = {'service_pages': [], 'homepage': None}
    for item in SERVICES:
        results['service_pages'].append(upsert_page(item))
    results['homepage'] = update_homepage(results['service_pages'])
    print(json.dumps(results, ensure_ascii=False))

if __name__ == '__main__':
    main()
