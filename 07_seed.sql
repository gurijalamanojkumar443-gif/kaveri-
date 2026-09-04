--3.9
INSERT INTO room(property_id,room_number,room_type_id)
VALUES
(1,'101',1),
(1,'102',1),
(1,'103',1),
(1,'104',2),
(1,'105',2),
(1,'106',2),
(1,'107',3),
(1,'108',3),
(1,'109',1),
(1,'110',1),
(1,'111',2),
(1,'112',3)
ON CONFLICT (property_id, room_number)
DO NOTHING;
select * from room;

--3.10
SELECT
    p.property_id,
    rt.room_type_id,
    s.start_date,
    s.end_date,
    CASE rt.type_name
        WHEN 'Standard' THEN s.base_rate
        WHEN 'Deluxe'   THEN s.base_rate * 1.35
        WHEN 'Suite'    THEN s.base_rate * 1.80
    END AS nightly_rate
FROM property p
CROSS JOIN room_type rt
CROSS JOIN (
    VALUES
        -- Regular season
        ('2025-01-01'::DATE,
         '2025-09-30'::DATE,
         4000::NUMERIC),
        -- Christmas peak season
        ('2025-10-01'::DATE,
         '2025-12-31'::DATE,
         6500::NUMERIC),
        -- Winter season
        ('2026-01-01'::DATE,
         '2026-03-31'::DATE,
         5000::NUMERIC)
) AS s(start_date, end_date, base_rate);

--3.12
INSERT INTO review (booking_id, rating, comment)
VALUES
    (1, 5, 'The view of the Nilgiri clouds from our balcony was sheer magic! Cozy fireplace and world-class hospitality.'),
    (2, 5, 'Perched at 7,200 feet, Kaveri Hilltop is the ultimate luxury getaway. The Victorian high tea and tea garden tour were unforgettable.'),
    (3, 5, 'Tranquil emerald waters and exceptional hospitality. The sunset private houseboat cruise was pure bliss.'),
    (4, 5, 'Waking up to the Cauvery River and the aroma of fresh estate coffee is unmatched. The Kodava cuisine was extraordinary!'),
    (7, 5, 'Riverfront villa with private plunge pool was stunning. Staff went above and beyond to organize our plantation safari.'),
    (10, 4, 'Very serene retreat by the backwaters. Fresh coastal seafood dining and the Ayurvedic herbal spa were revitalizing.'),
    (13, 5, 'Traditional Kerala architecture with five-star luxury. Sunrise yoga on the wooden lagoon deck is a must-do.'),
    (14, 5, 'Stunning tea valley views, roaring hearths, and immaculate service. Truly one of the finest heritage stays in India.'),
    (17, 5, 'Surrounded by 45 acres of coffee plantations. The guided wildlife trail and riverside candlelight dinner made our anniversary unforgettable.'),
    (18, 5, 'Gliding through Alleppey backwaters on their cedar houseboat with a personal chef was the highlight of our Kerala trip.'),
    (20, 4, 'Delightful colonial charm, eucalyptus crisp air, and attentive staff. Looking forward to returning next winter.'),
    (21, 5, 'Spectacular backwater sunset vistas. The plunge pool suite and coconut grove surroundings felt like paradise.'),
    (23, 5, 'Pure luxury in the Coorg rainforest. Hearing the river flow while enjoying authentic filter coffee was heavenly.'),
    (24, 5, 'Outstanding hilltop panorama! The private heated jacuzzi overlooking the valley at dusk was breathtaking.'),
    (25, 4, 'Exceptional heritage ambience, lavish buffet spreads, and wonderfully warm hospitality from the entire team.');
SELECT COUNT(*) AS total_reviews
FROM review;

--3.11
ALTER TABLE legacy_reservations
ADD CONSTRAINT unique_legacy_row_id UNIQUE (row_id);

INSERT INTO legacy_reservations VALUES
('31','Aarav Sharma','aarav.sharma@example.com','+91 98765 43210','Bengaluru','Kaveri Riverside','Coorg','4','103','Standard','2','2025-01-20','2025-01-23','3200','9600','card','confirmed','Repeat guest'),
('32','Anita Desai','anita.desai@example.com','+91 91234 56789','Mumbai','Kaveri Hilltop','Ooty','5','202','Deluxe','2','2025-01-25','2025-01-28','6800','20400','UPI','confirmed',''),
('33','Ben Carter','ben.carter@example.org','+44 7700 900123','Bristol','Kaveri Backwater','Alleppey','4','304','Standard','1','2025-02-01','2025-02-04','3900','11700','card','confirmed','Weekend stay'),
('34','Chloe Dubois','chloe.dubois@example.com','+33 6 12 34 56 78','Lyon','Kaveri Riverside','Coorg','4','105','Suite','2','2025-02-06','2025-02-10','7900','31600','upi','confirmed',''),
('35','Daniel Fischer','daniel.fischer@example.de','+49 151 12345678','Berlin','Kaveri Hilltop','Ooty','5','203','Deluxe','2','2025-02-12','2025-02-15','6800','20400','card','cancelled','Cancelled by guest'),
('36','Elena Rossi','elena.rossi@example.com','+39 320 1234567','Milan','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-02-18','2025-02-22','9500','38000','CARD','confirmed','Repeat guest'),
('37','Farhan Ali','farhan.ali@example.com','+91 99887 76655','Hyderabad','Kaveri Riverside','Coorg','4','101','Deluxe','2','2025-02-24','2025-02-27','4500','13500','upi','confirmed',''),
('38','Grace Okafor','grace.okafor@example.com','+234 802 123 4567','Lagos','Kaveri Hilltop','Ooty','5','204','Standard','1','2025-03-01','2025-03-04','5400','16200','card','no show','Did not arrive'),
('39','Hiroshi Tanaka','hiroshi.tanaka@example.jp','+81 90-1234-5678','Osaka','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2025-03-06','2025-03-10','5100','20400','UPI','confirmed','Airport pickup'),
('40','Isabel Moreno','isabel.moreno@example.com','+34 612 345 678','Madrid','Kaveri Hilltop','Ooty','5','201','Suite','3','2025-03-12','2025-03-16','8200','32800','Card','confirmed','Extra bed'),
('41','Jonas Weber','jonas.weber@example.de','+49 170 9876543','Hamburg','Kaveri Backwater','Alleppey','4','304','Standard','1','2025-03-18','2025-03-20','3900','7800','card','confirmed',''),
('42','Kavya Nair','kavya.nair@example.com','+91 94567 89012','Kochi','Kaveri Riverside','Coorg','4','102','Deluxe','2','2025-03-24','2025-03-27','4500','13500','UPI','confirmed','Repeat guest'),
('43','Liam O''Brien','liam.obrien@example.ie','+353 87 123 4567','Dublin','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2025-03-30','2025-04-03','6800','27200','card','confirmed',''),
('44','Maya Krishnan','maya.k@example.com','+91 98111 22334','Chennai','Kaveri Riverside','Coorg','4','104','Standard','2','2025-04-05','2025-04-08','3200','9600','CARD','confirmed',''),
('45','Noah Bergman','noah.bergman@example.se','+46 70 123 45 67','Stockholm','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-04-10','2025-04-14','9500','38000','card','confirmed','Repeat guest'),
('46','Priya Menon','priya.menon@example.com','+91 90000 11111','Kochi','Kaveri Hilltop','Ooty','5','202','Deluxe','2','2025-04-15','2025-04-18','6800','20400','upi','confirmed',''),
('47','Sofia Ahmed','sofia.ahmed@example.com','+91 93333 44444','Delhi','Kaveri Riverside','Coorg','4','101','Deluxe','2','2025-04-20','2025-04-23','4500','13500','Card','cancelled','Travel plans changed'),
('48','Tom Nguyen','tom.nguyen@example.com','+84 90 123 4567','Hanoi','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2025-04-25','2025-04-29','5100','20400','UPI','confirmed',''),
('49','Yusuf Demir','yusuf.demir@example.com','+90 532 123 4567','Istanbul','Kaveri Hilltop','Ooty','5','204','Standard','1','2025-05-01','2025-05-03','5400','10800','card','confirmed',''),
('50','Aarav Sharma','aarav.sharma@example.com','+91 98765 43210','Bengaluru','Kaveri Riverside','Coorg','4','105','Suite','2','2025-05-05','2025-05-09','7900','31600','UPI','confirmed','Third stay'),
('51','Anita Desai','anita.desai@example.com','+91 91234 56789','Mumbai','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2025-05-10','2025-05-13','5100','15300','card','confirmed','Repeat guest'),
('52','Ben Carter','ben.carter@example.org','+44 7700 900123','Bristol','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2025-05-15','2025-05-18','6800','20400','CARD','confirmed',''),
('53','Chloe Dubois','chloe.dubois@example.com','+33 6 12 34 56 78','Lyon','Kaveri Riverside','Coorg','4','103','Standard','2','2025-05-20','2025-05-23','3200','9600','upi','confirmed',''),
('54','Daniel Fischer','daniel.fischer@example.de','+49 151 12345678','Berlin','Kaveri Backwater','Alleppey','4','304','Standard','1','2025-05-25','2025-05-27','3900','7800','Bank Transfer','confirmed',''),
('55','Elena Rossi','elena.rossi@example.com','+39 320 1234567','Milan','Kaveri Hilltop','Ooty','5','201','Suite','2','2025-05-30','2025-06-03','8200','32800','Card','no show','Did not arrive'),
('56','Farhan Ali','farhan.ali@example.com','+91 99887 76655','Hyderabad','Kaveri Riverside','Coorg','4','102','Deluxe','2','2025-06-05','2025-06-08','4500','13500','UPI','confirmed',''),
('57','Grace Okafor','grace.okafor@example.com','+234 802 123 4567','Lagos','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2025-06-10','2025-06-14','5100','20400','card','confirmed','Repeat guest'),
('58','Hiroshi Tanaka','hiroshi.tanaka@example.jp','+81 90-1234-5678','Osaka','Kaveri Hilltop','Ooty','5','203','Deluxe','2','2025-06-15','2025-06-18','6800','20400','CARD','confirmed',''),
('59','Isabel Moreno','isabel.moreno@example.com','+34 612 345 678','Madrid','Kaveri Riverside','Coorg','4','104','Standard','2','2025-06-20','2025-06-23','3200','9600','upi','confirmed',''),
('60','Jonas Weber','jonas.weber@example.de','+49 170 9876543','Hamburg','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-06-25','2025-06-29','9500','38000','Card','confirmed',''),
('61','Kavya Nair','kavya.nair@example.com','+91 94567 89012','Kochi','Kaveri Hilltop','Ooty','5','202','Deluxe','2','2025-07-01','2025-07-04','6800','20400','UPI','confirmed','Repeat guest'),
('62','Liam O''Brien','liam.obrien@example.ie','+353 87 123 4567','Dublin','Kaveri Riverside','Coorg','4','101','Deluxe','2','2025-07-06','2025-07-09','4500','13500','card','confirmed',''),
('63','Maya Krishnan','maya.k@example.com','+91 98111 22334','Chennai','Kaveri Backwater','Alleppey','4','304','Standard','2','2025-07-11','2025-07-14','3900','11700','UPI','cancelled','Cancelled before arrival'),
('64','Noah Bergman','noah.bergman@example.se','+46 70 123 45 67','Stockholm','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2025-07-16','2025-07-20','6800','27200','card','confirmed',''),
('65','Priya Menon','priya.menon@example.com','+91 90000 11111','Kochi','Kaveri Riverside','Coorg','4','105','Suite','2','2025-07-21','2025-07-25','7900','31600','UPI','confirmed',''),
('66','Sofia Ahmed','sofia.ahmed@example.com','+91 93333 44444','Delhi','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2025-07-26','2025-07-29','5100','15300','card','confirmed','Repeat guest'),
('67','Tom Nguyen','tom.nguyen@example.com','+84 90 123 4567','Hanoi','Kaveri Hilltop','Ooty','5','204','Standard','1','2025-08-01','2025-08-03','5400','10800','CARD','confirmed',''),
('68','Yusuf Demir','yusuf.demir@example.com','+90 532 123 4567','Istanbul','Kaveri Riverside','Coorg','4','103','Standard','2','2025-08-06','2025-08-09','3200','9600','upi','confirmed',''),
('69','Aarav Sharma','aarav.sharma@example.com','+91 98765 43210','Bengaluru','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2025-08-11','2025-08-15','5100','20400','UPI','confirmed','Repeat guest'),
('70','Anita Desai','anita.desai@example.com','+91 91234 56789','Mumbai','Kaveri Hilltop','Ooty','5','201','Suite','2','2025-08-16','2025-08-20','8200','32800','card','confirmed',''),
('71','Ben Carter','ben.carter@example.org','+44 7700 900123','Bristol','Kaveri Riverside','Coorg','4','102','Deluxe','2','2025-08-21','2025-08-24','4500','13500','Card','no show','Did not arrive'),
('72','Chloe Dubois','chloe.dubois@example.com','+33 6 12 34 56 78','Lyon','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-08-26','2025-08-30','9500','38000','UPI','confirmed',''),
('73','Daniel Fischer','daniel.fischer@example.de','+49 151 12345678','Berlin','Kaveri Hilltop','Ooty','5','203','Deluxe','2','2025-09-01','2025-09-04','6800','20400','card','confirmed','Repeat guest'),
('74','Elena Rossi','elena.rossi@example.com','+39 320 1234567','Milan','Kaveri Riverside','Coorg','4','105','Suite','2','2025-09-06','2025-09-10','7900','31600','CARD','confirmed',''),
('75','Farhan Ali','farhan.ali@example.com','+91 99887 76655','Hyderabad','Kaveri Backwater','Alleppey','4','304','Standard','2','2025-09-11','2025-09-14','3900','11700','upi','cancelled','Cancelled by guest'),
('76','Grace Okafor','grace.okafor@example.com','+234 802 123 4567','Lagos','Kaveri Hilltop','Ooty','5','204','Standard','1','2025-09-16','2025-09-18','5400','10800','card','confirmed',''),
('77','Hiroshi Tanaka','hiroshi.tanaka@example.jp','+81 90-1234-5678','Osaka','Kaveri Riverside','Coorg','4','101','Deluxe','2','2025-09-21','2025-09-24','4500','13500','UPI','confirmed',''),
('78','Isabel Moreno','isabel.moreno@example.com','+34 612 345 678','Madrid','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2025-09-26','2025-09-30','5100','20400','card','confirmed','Repeat guest'),
('79','Jonas Weber','jonas.weber@example.de','+49 170 9876543','Hamburg','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2025-10-01','2025-10-05','6800','27200','CARD','confirmed',''),
('80','Kavya Nair','kavya.nair@example.com','+91 94567 89012','Kochi','Kaveri Riverside','Coorg','4','104','Standard','2','2025-10-06','2025-10-09','3200','9600','upi','confirmed',''),
('81','Liam O''Brien','liam.obrien@example.ie','+353 87 123 4567','Dublin','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2025-10-11','2025-10-15','5100','20400','card','confirmed','Repeat guest'),
('82','Maya Krishnan','maya.k@example.com','+91 98111 22334','Chennai','Kaveri Hilltop','Ooty','5','201','Suite','2','2025-10-16','2025-10-20','8200','32800','UPI','confirmed',''),
('83','Noah Bergman','noah.bergman@example.se','+46 70 123 45 67','Stockholm','Kaveri Riverside','Coorg','4','103','Standard','2','2025-10-21','2025-10-24','3200','9600','card','confirmed',''),
('84','Priya Menon','priya.menon@example.com','+91 90000 11111','Kochi','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-10-26','2025-10-30','9500','38000','Card','confirmed',''),
('85','Sofia Ahmed','sofia.ahmed@example.com','+91 93333 44444','Delhi','Kaveri Hilltop','Ooty','5','202','Deluxe','2','2025-11-01','2025-11-04','6800','20400','upi','confirmed','Repeat guest'),
('86','Tom Nguyen','tom.nguyen@example.com','+84 90 123 4567','Hanoi','Kaveri Riverside','Coorg','4','102','Deluxe','2','2025-11-06','2025-11-09','4500','13500','CARD','confirmed',''),
('87','Yusuf Demir','yusuf.demir@example.com','+90 532 123 4567','Istanbul','Kaveri Backwater','Alleppey','4','304','Standard','1','2025-11-11','2025-11-13','3900','7800','card','cancelled','Cancelled'),
('88','Aarav Sharma','aarav.sharma@example.com','+91 98765 43210','Bengaluru','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2025-11-16','2025-11-20','6800','27200','UPI','confirmed','Repeat guest'),
('89','Anita Desai','anita.desai@example.com','+91 91234 56789','Mumbai','Kaveri Riverside','Coorg','4','105','Suite','2','2025-11-21','2025-11-25','7900','31600','card','confirmed',''),
('90','Ben Carter','ben.carter@example.org','+44 7700 900123','Bristol','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2025-11-26','2025-11-29','5100','15300','UPI','confirmed',''),
('91','Chloe Dubois','chloe.dubois@example.com','+33 6 12 34 56 78','Lyon','Kaveri Hilltop','Ooty','5','203','Deluxe','2','2025-12-01','2025-12-04','6800','20400','card','confirmed','Repeat guest'),
('92','Daniel Fischer','daniel.fischer@example.de','+49 151 12345678','Berlin','Kaveri Riverside','Coorg','4','104','Standard','2','2025-12-05','2025-12-08','3200','9600','CARD','confirmed',''),
('93','Elena Rossi','elena.rossi@example.com','+39 320 1234567','Milan','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2025-12-09','2025-12-12','5100','15300','upi','confirmed',''),
('94','Farhan Ali','farhan.ali@example.com','+91 99887 76655','Hyderabad','Kaveri Hilltop','Ooty','5','204','Standard','1','2025-12-13','2025-12-16','5400','16200','card','confirmed',''),
('95','Grace Okafor','grace.okafor@example.com','+234 802 123 4567','Lagos','Kaveri Riverside','Coorg','4','101','Deluxe','2','2025-12-17','2025-12-20','4500','13500','UPI','no show','Did not arrive'),
('96','Hiroshi Tanaka','hiroshi.tanaka@example.jp','+81 90-1234-5678','Osaka','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-12-20','2025-12-24','12000','48000','card','confirmed','Christmas peak'),
('97','Isabel Moreno','isabel.moreno@example.com','+34 612 345 678','Madrid','Kaveri Riverside','Coorg','4','105','Suite','2','2025-12-21','2025-12-25','15800','63200','Card','confirmed','Christmas peak'),
('98','Jonas Weber','jonas.weber@example.de','+49 170 9876543','Hamburg','Kaveri Hilltop','Ooty','5','201','Suite','2','2025-12-22','2025-12-26','16400','65600','UPI','confirmed','Christmas peak'),
('99','Kavya Nair','kavya.nair@example.com','+91 94567 89012','Kochi','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2025-12-23','2025-12-27','10200','40800','card','confirmed','Christmas peak'),
('100','Liam O''Brien','liam.obrien@example.ie','+353 87 123 4567','Dublin','Kaveri Riverside','Coorg','4','102','Deluxe','2','2025-12-24','2025-12-28','9000','36000','CARD','confirmed','Christmas peak'),
('101','Maya Krishnan','maya.k@example.com','+91 98111 22334','Chennai','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2025-12-25','2025-12-29','13600','54400','upi','confirmed','Christmas holiday'),
('102','Noah Bergman','noah.bergman@example.se','+46 70 123 45 67','Stockholm','Kaveri Backwater','Alleppey','4','304','Standard','1','2025-12-26','2025-12-29','7800','23400','card','cancelled','Christmas cancellation'),
('103','Priya Menon','priya.menon@example.com','+91 90000 11111','Kochi','Kaveri Riverside','Coorg','4','103','Standard','2','2025-12-27','2025-12-30','6400','19200','UPI','confirmed',''),
('104','Sofia Ahmed','sofia.ahmed@example.com','+91 93333 44444','Delhi','Kaveri Hilltop','Ooty','5','202','Deluxe','2','2025-12-28','2025-12-31','13600','40800','card','confirmed','Christmas peak'),
('105','Tom Nguyen','tom.nguyen@example.com','+84 90 123 4567','Hanoi','Kaveri Backwater','Alleppey','4','303','Suite','2','2025-12-29','2026-01-02','12000','48000','CARD','confirmed','New Year stay'),
('106','Yusuf Demir','yusuf.demir@example.com','+90 532 123 4567','Istanbul','Kaveri Riverside','Coorg','4','101','Deluxe','2','2026-01-05','2026-01-08','4500','13500','upi','confirmed',''),
('107','Aarav Sharma','aarav.sharma@example.com','+91 98765 43210','Bengaluru','Kaveri Hilltop','Ooty','5','203','Deluxe','2','2026-01-10','2026-01-13','6800','20400','UPI','confirmed','Repeat guest'),
('108','Anita Desai','anita.desai@example.com','+91 91234 56789','Mumbai','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2026-01-15','2026-01-18','5100','15300','card','confirmed',''),
('109','Ben Carter','ben.carter@example.org','+44 7700 900123','Bristol','Kaveri Riverside','Coorg','4','104','Standard','2','2026-01-20','2026-01-23','3200','9600','CARD','confirmed','Repeat guest'),
('110','Chloe Dubois','chloe.dubois@example.com','+33 6 12 34 56 78','Lyon','Kaveri Hilltop','Ooty','5','205','Deluxe','2','2026-01-25','2026-01-28','6800','20400','upi','confirmed',''),
('111','Daniel Fischer','daniel.fischer@example.de','+49 151 12345678','Berlin','Kaveri Backwater','Alleppey','4','304','Standard','1','2026-02-01','2026-02-03','3900','7800','card','confirmed',''),
('112','Elena Rossi','elena.rossi@example.com','+39 320 1234567','Milan','Kaveri Riverside','Coorg','4','105','Suite','2','2026-02-06','2026-02-10','7900','31600','UPI','confirmed','Repeat guest'),
('113','Farhan Ali','farhan.ali@example.com','+91 99887 76655','Hyderabad','Kaveri Hilltop','Ooty','5','204','Standard','1','2026-02-11','2026-02-14','5400','16200','card','cancelled','Cancelled'),
('114','Grace Okafor','grace.okafor@example.com','+234 802 123 4567','Lagos','Kaveri Backwater','Alleppey','4','301','Deluxe','2','2026-02-16','2026-02-19','5100','15300','UPI','confirmed','Repeat guest'),
('115','Hiroshi Tanaka','hiroshi.tanaka@example.jp','+81 90-1234-5678','Osaka','Kaveri Riverside','Coorg','4','102','Deluxe','2','2026-02-21','2026-02-24','4500','13500','card','confirmed',''),
('116','Isabel Moreno','isabel.moreno@example.com','+34 612 345 678','Madrid','Kaveri Hilltop','Ooty','5','201','Suite','3','2026-02-26','2026-03-02','8200','32800','UPI','confirmed',''),
('117','Jonas Weber','jonas.weber@example.de','+49 170 9876543','Hamburg','Kaveri Backwater','Alleppey','4','303','Suite','2','2026-03-03','2026-03-07','9500','38000','card','no show','Did not arrive'),
('118','Kavya Nair','kavya.nair@example.com','+91 94567 89012','Kochi','Kaveri Riverside','Coorg','4','103','Standard','2','2026-03-08','2026-03-11','3200','9600','CARD','confirmed','Repeat guest'),
('119','Liam O''Brien','liam.obrien@example.ie','+353 87 123 4567','Dublin','Kaveri Hilltop','Ooty','5','202','Deluxe','2','2026-03-13','2026-03-16','6800','20400','upi','confirmed',''),
('120','Maya Krishnan','maya.k@example.com','+91 98111 22334','Chennai','Kaveri Backwater','Alleppey','4','302','Deluxe','2','2026-03-18','2026-03-21','5100','15300','card','confirmed','Repeat guest')

ON CONFLICT (row_id) DO NOTHING;
select * from legacy_reservations;
