WEIERSTRASS   = "weierstrass"
TWISTEDEDWARD = "twistededward"
MONTGOMERY     = "montgomery"


curves = [

    {
        'name':      "stark256",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0x0800000000000011000000000000000000000000000000000000000000000001,
        'generator': (0x01ef15c18599971b7beced415a40f0c7deacfd9b0d1819e03d723d8bc943cfca,
                      0x005668060aa49730b7be4801df46ec62de53ecd11abe43a32873000c36e8dc1f),
        'order':     0x0800000000000010ffffffffffffffffb781126dcae7b2321e66a241adc64d2f,
        'cofactor':  1,
        'a':         0x0000000000000000000000000000000000000000000000000000000000000001,
        'b':         0x06f21413efbe40de150e596d72f7a8c5609ad26c15c915c1f4cdfcb99cee9e89,

    },

    {
        'name':      "frp256v1",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xF1FD178C0B3AD58F10126DE8CE42435B3961ADBCABC8CA6DE8FCF353D86E9C03,
        'generator': (0xB6B3D4C356C139EB31183D4749D423958C27D2DCAF98B70164C97A2DD98F5CFF,
                      0x6142E0F7C8B204911F9271F0F3ECEF8C2701C307E8E4C9E183115A1554062CFB),
        'order':     0xF1FD178C0B3AD58F10126DE8CE42435B53DC67E140D2BF941FFDD459C6D655E1,
        'cofactor':  1,
        'a':         0xF1FD178C0B3AD58F10126DE8CE42435B3961ADBCABC8CA6DE8FCF353D86E9C00,
        'b':         0xEE353FCA5428A9300D4ABA754A44C00FDFEC0C9AE4B1A1803075ED967B7BB73F,

    },

    {
        'name':      "secp521r1",
        'type':      WEIERSTRASS,
        'size':      521,
        'field':     0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
        'generator': (0x00C6858E06B70404E9CD9E3ECB662395B4429C648139053FB521F828AF606B4D3DBAA14B5E77EFE75928FE1DC127A2FFA8DE3348B3C1856A429BF97E7E31C2E5BD66,
                      0x011839296A789A3BC0045C8A5FB42C7D1BD998F54449579B446817AFBD17273E662C97EE72995EF42640C550B9013FAD0761353C7086A272C24088BE94769FD16650),
        'order':     0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFA51868783BF2F966B7FCC0148F709A5D03BB5C9B8899C47AEBB6FB71E91386409,
        'cofactor':  1,
        'a':         0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC,
        'b':         0x0051953EB9618E1C9A1F929A21A0B68540EEA2DA725B99B315F3B8B489918EF109E156193951EC7E937B1652C0BD3BB1BF073573DF883D2C34F1EF451FD46B503F00,

    },

    {
        'name':      "secp384r1",
        'type':      WEIERSTRASS,
        'size':      384,
        'field':     0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffff0000000000000000ffffffff,
        'generator': (0xaa87ca22be8b05378eb1c71ef320ad746e1d3b628ba79b9859f741e082542a385502f25dbf55296c3a545e3872760ab7,
                      0x3617de4a96262c6f5d9e98bf9292dc29f8f41dbd289a147ce9da3113b5f0b8c00a60b1ce1d7e819d7a431d7c90ea0e5f),
        'order':     0xffffffffffffffffffffffffffffffffffffffffffffffffc7634d81f4372ddf581a0db248b0a77aecec196accc52973,
        'cofactor':  1,
        'a':         0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffff0000000000000000fffffffc,
        'b':         0xb3312fa7e23ee7e4988e056be3f82d19181d9c6efe8141120314088f5013875ac656398d8a2ed19d2a85c8edd3ec2aef,

    },

    {
        'name':      "secp256k1",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f,
        'generator': (0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798,
                      0x483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8),
        'order':     0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141,
        'cofactor':  1,
        'a':         0,
        'b':         7

    },

    {
        'name':      "secp256r1",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff,
        'generator': (0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296,
                      0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5),
        'order':     0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551,
        'cofactor':  0x1,
        'a':         0xffffffff00000001000000000000000000000000fffffffffffffffffffffffc,
        'b':         0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
    },

    {
        'name':      "secp224k1",
        'type':      WEIERSTRASS,
        'size':      224,
        'field':     0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFE56D,
        'generator': (0xA1455B334DF099DF30FC28A169A467E9E47075A90F7E650EB6B7A45C,
                      0x7E089FED7FBA344282CAFBD6F7E319F7C0B0BD59E2CA4BDB556D61A5),
        'order':     0x010000000000000000000000000001DCE8D2EC6184CAF0A971769FB1F7,
        'cofactor':  0x1,
        'a':         0x0,
        'b':         0x5,
    },

    {
        'name':      "secp224r1",
        'type':      WEIERSTRASS,
        'size':      224,
        'field':     0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF000000000000000000000001,
        'generator': (0xB70E0CBD6BB4BF7F321390B94A03C1D356C21122343280D6115C1D21 ,
                      0xBD376388B5F723FB4C22DFE6CD4375A05A07476444D5819985007E34),
        'order':     0xFFFFFFFFFFFFFFFFFFFFFFFFFFFF16A2E0B8F03E13DD29455C5C2A3D,
        'cofactor':  0x1,
        'a':         0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFE,
        'b':         0xB4050A850C04B3ABF54132565044B0B7D7BFD8BA270B39432355FFB4
    },


    {
        'name':      "secp192k1",
        'type':      WEIERSTRASS,
        'size':      192,
        'field':     0xfffffffffffffffffffffffffffffffffffffffeffffee37,
        'generator': (0xdb4ff10ec057e9ae26b07d0280b7f4341da5d1b1eae06c7d,
                      0x9b2f2f6d9c5628a7844163d015be86344082aa88d95e2f9d),
        'order':     0xfffffffffffffffffffffffe26f2fc170f69466a74defd8d,
        'cofactor':  0x1,
        'a':         0x0,
        'b':         0x3
    },

    {
        'name':      "secp192r1",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xfffffffffffffffffffffffffffffffeffffffffffffffff,
        'generator': (0x188da80eb03090f67cbf20eb43a18800f4ff0afd82ff1012,
                      0x7192b95ffc8da78631011ed6b24cdd573f977a11e794811),
        'order':     0xffffffffffffffffffffffff99def836146bc9b1b4d22831,
        'cofactor':  0x1,
        'a':         0xfffffffffffffffffffffffffffffffefffffffffffffffc,
        'b':         0x64210519e59c80e70fa7e9ab72243049feb8deecc146b9b1
    },


    {
        'name':      "secp160k1",
        'type':      WEIERSTRASS,
        'size':      160,
        'field':     0xfffffffffffffffffffffffffffffffeffffac73,
        'generator': (0x3b4c382ce37aa192a4019e763036f4f5dd4d7ebb,
                      0x938cf935318fdced6bc28286531733c3f03c4fee),
        'order':     0x100000000000000000001b8fa16dfab9aca16b6b3,
        'cofactor':  0x1,
        'a':         0x0,
        'b':         0x7
    },

    {
        'name':      "secp160r1",
        'type':      WEIERSTRASS,
        'size':      160,
        'field':     0xffffffffffffffffffffffffffffffff7fffffff,
        'generator': (0x4a96b5688ef573284664698968c38bb913cbfc82,
                      0x23a628553168947d59dcc912042351377ac5fb32),
        'order':     0x100000000000000000001f4c8f927aed3ca752257,
        'cofactor':  0x1,
        'a':         0xffffffffffffffffffffffffffffffff7ffffffc,
        'b':         0x1c97befc54bd7a8b65acf89f81d4d4adc565fa45
    },

    {
        'name':      "secp160r2",
        'type':      WEIERSTRASS,
        'size':      160,
        'field':     0xfffffffffffffffffffffffffffffffeffffac73,
        'generator': (0x52dcb034293a117e1f4ff11b30f7199d3144ce6d,
                      0xfeaffef2e331f296e071fa0df9982cfea7d43f2e),
        'order':     0x100000000000000000000351ee786a818f3a1a16b,
        'cofactor':  0x1,
        'a':         0xfffffffffffffffffffffffffffffffeffffac70,
        'b':         0xb4e134d3fb59eb8bab57274904664d5af50388ba
    },

    {
        'name':      "Brainpool-p512t1",
        'type':      WEIERSTRASS,
        'size':      512,
        'field':     0xAADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA703308717D4D9B009BC66842AECDA12AE6A380E62881FF2F2D82C68528AA6056583A48F3,
        'generator': (0x640ECE5C12788717B9C1BA06CBC2A6FEBA85842458C56DDE9DB1758D39C0313D82BA51735CDB3EA499AA77A7D6943A64F7A3F25FE26F06B51BAA2696FA9035DA,
                      0x5B534BD595F5AF0FA2C892376C84ACE1BB4E3019B71634C01131159CAE03CEE9D9932184BEEF216BD71DF2DADF86A627306ECFF96DBB8BACE198B61E00F8B332),
        'order':     0xAADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA70330870553E5C414CA92619418661197FAC10471DB1D381085DDADDB58796829CA90069,
        'cofactor':  1,
        'a':         0xAADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA703308717D4D9B009BC66842AECDA12AE6A380E62881FF2F2D82C68528AA6056583A48F0,
        'b':         0x7CBBBCF9441CFAB76E1890E46884EAE321F70C0BCB4981527897504BEC3E36A62BCDFA2304976540F6450085F2DAE145C22553B465763689180EA2571867423E,

    },

    {
        'name':      "Brainpool-p512r1",
        'type':      WEIERSTRASS,
        'size':      512,
        'field':     0xAADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA703308717D4D9B009BC66842AECDA12AE6A380E62881FF2F2D82C68528AA6056583A48F3,
        'generator': (0x81AEE4BDD82ED9645A21322E9C4C6A9385ED9F70B5D916C1B43B62EEF4D0098EFF3B1F78E2D0D48D50D1687B93B97D5F7C6D5047406A5E688B352209BCB9F822,
                      0x7DDE385D566332ECC0EABFA9CF7822FDF209F70024A57B1AA000C55B881F8111B2DCDE494A5F485E5BCA4BD88A2763AED1CA2B2FA8F0540678CD1E0F3AD80892),
        'order':     0xAADD9DB8DBE9C48B3FD4E6AE33C9FC07CB308DB3B3C9D20ED6639CCA70330870553E5C414CA92619418661197FAC10471DB1D381085DDADDB58796829CA90069,
        'cofactor':  1,
        'a':         0x7830A3318B603B89E2327145AC234CC594CBDD8D3DF91610A83441CAEA9863BC2DED5D5AA8253AA10A2EF1C98B9AC8B57F1117A72BF2C7B9E7C1AC4D77FC94CA,
        'b':         0x3DF91610A83441CAEA9863BC2DED5D5AA8253AA10A2EF1C98B9AC8B57F1117A72BF2C7B9E7C1AC4D77FC94CADC083E67984050B75EBAE5DD2809BD638016F723,

    },

    {
        'name':      "Brainpool-p384t1",
        'type':      WEIERSTRASS,
        'size':      384,
        'field':     0x8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B412B1DA197FB71123ACD3A729901D1A71874700133107EC53,
        'generator': (0x18DE98B02DB9A306F2AFCD7235F72A819B80AB12EBD653172476FECD462AABFFC4FF191B946A5F54D8D0AA2F418808CC,
                      0x25AB056962D30651A114AFD2755AD336747F93475B7A1FCA3B88F2B6A208CCFE469408584DC2B2912675BF5B9E582928),
        'order':     0x8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B31F166E6CAC0425A7CF3AB6AF6B7FC3103B883202E9046565,
        'cofactor':  1,
        'a':         0x8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B412B1DA197FB71123ACD3A729901D1A71874700133107EC50,
        'b':         0x7F519EADA7BDA81BD826DBA647910F8C4B9346ED8CCDC64E4B1ABD11756DCE1D2074AA263B88805CED70355A33B471EE,

    },

    {
        'name':      "Brainpool-p384r1",
        'type':      WEIERSTRASS,
        'size':      384,
        'field':     0x8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B412B1DA197FB71123ACD3A729901D1A71874700133107EC53,
        'generator': (0x1D1C64F068CF45FFA2A63A81B7C13F6B8847A3E77EF14FE3DB7FCAFE0CBD10E8E826E03436D646AAEF87B2E247D4AF1E,
                      0x8ABE1D7520F9C2A45CB1EB8E95CFD55262B70B29FEEC5864E19C054FF99129280E4646217791811142820341263C5315),
        'order':     0x8CB91E82A3386D280F5D6F7E50E641DF152F7109ED5456B31F166E6CAC0425A7CF3AB6AF6B7FC3103B883202E9046565,
        'cofactor':  1,
        'a':         0x7BC382C63D8C150C3C72080ACE05AFA0C2BEA28E4FB22787139165EFBA91F90F8AA5814A503AD4EB04A8C7DD22CE2826,
        'b':         0x04A8C7DD22CE28268B39B55416F0447C2FB77DE107DCD2A62E880EA53EEB62D57CB4390295DBC9943AB78696FA504C11,

    },

    {
        'name':      "Brainpool-p320t1",
        'type':      WEIERSTRASS,
        'size':      320,
        'field':     0xD35E472036BC4FB7E13C785ED201E065F98FCFA6F6F40DEF4F92B9EC7893EC28FCD412B1F1B32E27,
        'generator': (0x925BE9FB01AFC6FB4D3E7D4990010F813408AB106C4F09CB7EE07868CC136FFF3357F624A21BED52,
                      0x63BA3A7A27483EBF6671DBEF7ABB30EBEE084E58A0B077AD42A5A0989D1EE71B1B9BC0455FB0D2C3),
        'order':     0xD35E472036BC4FB7E13C785ED201E065F98FCFA5B68F12A32D482EC7EE8658E98691555B44C59311,
        'cofactor':  1,
        'a':         0xD35E472036BC4FB7E13C785ED201E065F98FCFA6F6F40DEF4F92B9EC7893EC28FCD412B1F1B32E24,
        'b':         0xA7F561E038EB1ED560B3D147DB782013064C19F27ED27C6780AAF77FB8A547CEB5B4FEF422340353,

    },

    {
        'name':      "Brainpool-p320r1",
        'type':      WEIERSTRASS,
        'size':      320,
        'field':     0xD35E472036BC4FB7E13C785ED201E065F98FCFA6F6F40DEF4F92B9EC7893EC28FCD412B1F1B32E27,
        'generator': (0x43BD7E9AFB53D8B85289BCC48EE5BFE6F20137D10A087EB6E7871E2A10A599C710AF8D0D39E20611,
                      0x14FDD05545EC1CC8AB4093247F77275E0743FFED117182EAA9C77877AAAC6AC7D35245D1692E8EE1),
        'order':     0xD35E472036BC4FB7E13C785ED201E065F98FCFA5B68F12A32D482EC7EE8658E98691555B44C59311,
        'cofactor':  1,
        'a':         0x3EE30B568FBAB0F883CCEBD46D3F3BB8A2A73513F5EB79DA66190EB085FFA9F492F375A97D860EB4,
        'b':         0x520883949DFDBC42D3AD198640688A6FE13F41349554B49ACC31DCCD884539816F5EB4AC8FB1F1A6,

    },

    {
        'name':      "Brainpool-p256r1",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xa9fb57dba1eea9bc3e660a909d838d726e3bf623d52620282013481d1f6e5377,
        'generator': (0x8bd2aeb9cb7e57cb2c4b482ffc81b7afb9de27e1e3bd23c23a4453bd9ace3262,
                      0x547ef835c3dac4fd97f8461a14611dc9c27745132ded8e545c1d54c72f046997),
        'order':     0xa9fb57dba1eea9bc3e660a909d838d718c397aa3b561a6f7901e0e82974856a7,
        'cofactor':  0x1,
        'a':         0x7d5a0975fc2c3057eef67530417affe7fb8055c126dc5c6ce94a4b44f330b5d9,
        'b':         0x26dc5c6ce94a4b44f330b5d9bbd77cbf958416295cf7e1ce6bccdc18ff8c07b6
    },

    {
        'name':      "Brainpool-p256t1",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xa9fb57dba1eea9bc3e660a909d838d726e3bf623d52620282013481d1f6e5377,
        'generator': (0xa3e8eb3cc1cfe7b7732213b23a656149afa142c47aafbc2b79a191562e1305f4,
                      0x2d996c823439c56d7f7b22e14644417e69bcb6de39d027001dabe8f35b25c9be),
        'order':     0xa9fb57dba1eea9bc3e660a909d838d718c397aa3b561a6f7901e0e82974856a7,
        'cofactor':  0x1,
        'a':         0xa9fb57dba1eea9bc3e660a909d838d726e3bf623d52620282013481d1f6e5374,
        'b':         0x662c61c430d84ea4fe66a7733d0b76b7bf93ebc4af2f49256ae58101fee92b04
    },

    {
        'name':      "Brainpool-p224r1",
        'type':      WEIERSTRASS,
        'size':      224,
        'field':     0xD7C134AA264366862A18302575D1D787B09F075797DA89F57EC8C0FF,
        'generator': (0x0D9029AD2C7E5CF4340823B2A87DC68C9E4CE3174C1E6EFDEE12C07D,
                      0x58AA56F772C0726F24C6B89E4ECDAC24354B9E99CAA3F6D3761402CD),
        'order':     0xD7C134AA264366862A18302575D0FB98D116BC4B6DDEBCA3A5A7939F,
        'cofactor':  0x1,
        'a':         0x68A5E62CA9CE6C1C299803A6C1530B514E182AD8B0042A59CAD29F43,
        'b':         0x2580F63CCFE44138870713B1A92369E33E2135D266DBB372386C400B
    },

    {
        'name':      "Brainpool-p224t1",
        'type':      WEIERSTRASS,
        'size':      224,
        'a':         0xD7C134AA264366862A18302575D1D787B09F075797DA89F57EC8C0FC,
        'b':         0x4B337D934104CD7BEF271BF60CED1ED20DA14C08B3BB64F18A60888D,
        'field':     0xD7C134AA264366862A18302575D1D787B09F075797DA89F57EC8C0FF,
        'generator': (0x6AB1E344CE25FF3896424E7FFE14762ECB49F8928AC0C76029B4D580,
                      0x0374E9F5143E568CD23F3F4D7C0D4B1E41C8CC0D1C6ABD5F1A46DB4C),
        'order':     0xD7C134AA264366862A18302575D0FB98D116BC4B6DDEBCA3A5A7939F,
        'cofactor':   0x1,
    },

    {
        'name':      "Brainpool-p192r1",
        'type':      WEIERSTRASS,
        'size':      192,
        'field':     0xc302f41d932a36cda7a3463093d18db78fce476de1a86297,
        'generator': (0xc0a0647eaab6a48753b033c56cb0f0900a2f5c4853375fd6,
                      0x14b690866abd5bb88b5f4828c1490002e6773fa2fa299b8f),
        'order':     0xc302f41d932a36cda7a3462f9e9e916b5be8f1029ac4acc1,
        'cofactor':  0x1,
        'a':         0x6a91174076b1e0e19c39c031fe8685c1cae040e5c69a28ef,
        'b':         0x469a28ef7c28cca3dc721d044f4496bcca7ef4146fbf25c9
    },

    {
        'name':      "Brainpool-p192t1",
        'type':      WEIERSTRASS,
        'size':      192,
        'field':     0xc302f41d932a36cda7a3463093d18db78fce476de1a86297,
        'generator': (0x3ae9e58c82f63c30282e1fe7bbf43fa72c446af6f4618129,
                      0x97e2c5667c2223a902ab5ca449d0084b7e5b3de7ccc01c9),
        'order':     0xc302f41d932a36cda7a3462f9e9e916b5be8f1029ac4acc1,
        'cofactor':  0x1,
        'a':         0xc302f41d932a36cda7a3463093d18db78fce476de1a86294,
        'b':         0x13d56ffaec78681e68f9deb43b35bec2fb68542e27897b79
    },

    {
        'name':      "Brainpool-p160r1",
        'type':      WEIERSTRASS,
        'size':      160,
        'field':     0xe95e4a5f737059dc60dfc7ad95b3d8139515620f,
        'generator': (0xbed5af16ea3f6a4f62938c4631eb5af7bdbcdbc3,
                      0x1667cb477a1a8ec338f94741669c976316da6321),
        'order':     0xe95e4a5f737059dc60df5991d45029409e60fc09,
        'cofactor':  0x1,
        'a':         0x340e7be2a280eb74e2be61bada745d97e8f7c300,
        'b':         0x1e589a8595423412134faa2dbdec95c8d8675e58
    },

    {
        'name':      "Brainpool-p160t1",
        'type':      WEIERSTRASS,
        'size':      160,
        'field':     0xe95e4a5f737059dc60dfc7ad95b3d8139515620f,
        'generator': (0xb199b13b9b34efc1397e64baeb05acc265ff2378,
                      0xadd6718b7c7c1961f0991b842443772152c9e0ad),
        'order':     0xe95e4a5f737059dc60df5991d45029409e60fc09,
        'cofactor':  0x1,
        'a':         0xe95e4a5f737059dc60dfc7ad95b3d8139515620c,
        'b':         0x7a556b6dae535b7b51ed2c4d7daa7a0b5c55f380
    },

    {
        'name':      "NIST-P256",
        'type':      WEIERSTRASS,
        'size':      256,
        'field':     0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff,
        'generator': (0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296,
                      0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5),
        'order':     0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551,
        'cofactor':  0x1,
        'a':         0xffffffff00000001000000000000000000000000fffffffffffffffffffffffc,
        'b':         0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
    },

    {
        'name':      "NIST-P224",
        'type':      WEIERSTRASS,
        'size':      224,
        'field':     0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF000000000000000000000001,
        'generator': (0xB70E0CBD6BB4BF7F321390B94A03C1D356C21122343280D6115C1D21 ,
                      0xBD376388B5F723FB4C22DFE6CD4375A05A07476444D5819985007E34),
        'order':     0xFFFFFFFFFFFFFFFFFFFFFFFFFFFF16A2E0B8F03E13DD29455C5C2A3D,
        'cofactor':  0x1,
        'a':         0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFE,
        'b':         0xB4050A850C04B3ABF54132565044B0B7D7BFD8BA270B39432355FFB4
    },

    {
        'name':      "NIST-P192",
        'type':      WEIERSTRASS,
        'size':      192,
        'field':     0xfffffffffffffffffffffffffffffffeffffffffffffffff,
        'generator': (0x188da80eb03090f67cbf20eb43a18800f4ff0afd82ff1012,
                      0x07192b95ffc8da78631011ed6b24cdd573f977a11e794811),
        'order':     0xffffffffffffffffffffffff99def836146bc9b1b4d22831,
        'cofactor':  0x1,
        'a':         0xfffffffffffffffffffffffffffffffefffffffffffffffc,
        'b':         0x64210519e59c80e70fa7e9ab72243049feb8deecc146b9b1
    },

    {
        'name':      "Ed448",
        'type':      TWISTEDEDWARD,
        'size':      448,
        'field':     0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffffffffffffffffffffffffffffffffffffffffffffffffffff,
        'generator': (0x4f1970c66bed0ded221d15a622bf36da9e146570470f1767ea6de324a3d3a46412ae1af72ab66511433b80e18b00938e2626a82bc70cc05e,
                      0x693f46716eb6bc248876203756c9c7624bea73736ca3984087789c1e05a0c2d73ad3ff1ce67c39c4fdbd132c4ed7c8ad9808795bf230fa14),
        'order':     0x3fffffffffffffffffffffffffffffffffffffffffffffffffffffff7cca23e9c44edb49aed63690216cc2728dc58f552378c292ab5844f3,
        'cofactor':  4,
        'd':         0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffffffffffffffffffffffffffffffffffffffffffffffff6756,
        'a':         1
    },

    {
        'name':      "Ed25519",
        'type':      TWISTEDEDWARD,
        'size':      256,
        'field':     0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffed,
        'generator': (15112221349535400772501151409588531511454012693041857206046113283949847762202,
                      46316835694926478169428394003475163141307993866256225615783033603165251855960),
        'order':     0x1000000000000000000000000000000014DEF9DEA2F79CD65812631A5CF5D3ED,
        'cofactor':  0x08,
        'd':         0x52036cee2b6ffe738cc740797779e89800700a4d4141d8ab75eb4dca135978a3,
        'a':         -1
    },

    {
        'name':      "Curve448",
        'type':      MONTGOMERY,
        'size':      448,
        'field':     0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffeffffffffffffffffffffffffffffffffffffffffffffffffffffffff,
        'generator': (5,
                      0x7d235d1295f5b1f66c98ab6e58326fcecbae5d34f55545d060f75dc28df3f6edb8027e2346430d211312c4b150677af76fd7223d457b5b1a),
        'order':     0x3fffffffffffffffffffffffffffffffffffffffffffffffffffffff7cca23e9c44edb49aed63690216cc2728dc58f552378c292ab5844f3,
        'cofactor':  4,
        'b':         1,
        'a':         0x262a6
    },

    {
        'name':      "Curve25519",
        'type':      MONTGOMERY,
        'size':      256,
        'field':     0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffed,
        'generator': (9,
                      43114425171068552920764898935933967039370386198203806730763910166200978582548),
        'order':     0x1000000000000000000000000000000014DEF9DEA2F79CD65812631A5CF5D3ED,
        'cofactor':  0x08,
        'b':         1,
        'a':         486662
    },
]
