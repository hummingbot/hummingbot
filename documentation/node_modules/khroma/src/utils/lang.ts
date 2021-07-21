
/* LANG */

const Lang = {

  round: ( number: number ): number => { // 10 digits rounding

    return Math.round ( number * 10000000000 ) / 10000000000;

  }

};

/* EXPORT */

export default Lang;
