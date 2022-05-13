/*
    Copyright 2007 Matt Fellows 
    
    Email:				Matt.Fellows@onegeek.com.au
    Web:				http://www.onegeek.com.au
    Acknowledgements:  
         				* http://dotnetremoting.com/ for the original idea
         				* John Griffin <john.griffin@vardentech.com> for some updates for recursive object levels
    License:            GNU GENERAL PUBLIC LICENSE
    TODO:               * Add in simple string serialization option
                        * Reduce size 
                        * Implement passing parameters into serialized functions (currently only supports no-argument functions)
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    
*/
/**
 * Create the ONEGEEK global namespace object
 * 
 * @package ONEGEEK
 */

const DOMParser = require('@xmldom/xmldom').DOMParser;

if (typeof (ONEGEEK) == "undefined") {
  /**
   * The ONEGEEK global namespace object.
   * 
   * @class ONEGEEK
   */
  ONEGEEK = {};
}

/**
 * Serialize/Deserializer any JavaScript object to a valid XML String (NOT JSON)
 * 
 * @class ONEGEEK.GSerializer
 */
ONEGEEK.GSerializer = function() {
  
  /* Private members */
  // var isIE = navigator.userAgent.toLowerCase().indexOf("msie") > -1;
  var isIE = false;
  // var isMoz = document.implementation && document.implementation.createDocument;
  
  // Unused parameters
  var use_encryption = false;
  var use_compression = false;
 
  /**
   * Serialize a JS object into an XML String for storage / transmission
   * (i.e. cookie, download etc.)
   * 
   * @function {public String} serialize
   * @param {Object} objectToSerialize - The object to be serialized
   * @param {Object} objectName - (Optional) Name of the object being passed in
   * @param {Object} indentSpace - (Optional) Use this as an indentSpace
   * @return {String} An String (XML document compressed and/or encrypted) specifying the object
   */
  this.serialize = function(objectToSerialize, objectName, indentSpace) {
     indentSpace = indentSpace?indentSpace:'';
     
     // Get object type name to serialize
     var type = getTypeName(objectToSerialize);
     
     // string to store serialized XML
     var s = indentSpace  + '<' + objectName +  ' type="' + type + '">';
  
     switch(type) {
      case "number":
      case "string":
      case "boolean": 
        s += objectToSerialize; 
        break;       
      case "date":
        s += objectToSerialize.toLocaleString(); 
        break;       
      case "Function":
          s += "\n";        
          s += "<![CDATA["+objectToSerialize+"]]>";
          s += indentSpace;
          break;            
      case "array": 
    	  s += "\n";          
	      for(var a in objectToSerialize){
	        s += this.serialize(objectToSerialize[a], ('index' + a ), indentSpace + "   ");
	      }
	      s += indentSpace;      
	      break;          
      default:
        s += "\n";
        
        for ( var o in objectToSerialize) {
          s += this.serialize(objectToSerialize[o], o, indentSpace + "   ");
        }        
        s += indentSpace;
        break;  
     }
     
    s += "</" + objectName + ">\n"; 
       
      return s;
  };
  
  /**
   * Deserialize a serialized XML object into a javascript object
   * Uses deserial recursively to rebuild the javascript
   * 
   * @function {public Object} deserialize
   * @see deserial
   * @param {Object} XmlText
   * @return {Object}
   */
  this.deserialize = function(XmlText) {
    var _doc = getDom(XmlText); 
    return deserial(_doc.childNodes[0]);
  };
  
  /**
   * Get the DOM object from an XML doc
   * NB: Works for IE and Mozilla
   * 
   * @function {private String} getDom
   * @param {Object} strXml
   * @return {Object} The browser specific DOM object 
   */
  function getDom(strXml) {
    var _doc = null;
  
    if (isIE) {
      _doc = new ActiveXObject("Msxml2.DOMDocument.3.0");
      _doc.loadXML(strXml); 
    }
    else {
      var parser = new DOMParser();
      _doc = parser.parseFromString(strXml, "text/xml");
    }
  
    return _doc;
  }
  
  /**
   * Deserialize an XML DOM object into a javascript object
   * 
   * NB: This function uses recursion
   * @function {private Object} deserial
   * @param {Object} domObject - The DOM object to deserialize into a JS Object
   * @return {Object} The deserialized object
   */
  function deserial(domObject) {
    var retObj; 
    var nodeType = getNodeType(domObject);
     
    if (isSimpleVar(nodeType)) {
      if (isIE) {
        return stringToObject(domObject.text, nodeType);
      }
      else {
        return stringToObject(domObject.textContent, nodeType);
      }
    }
    
    switch(nodeType) {
      case "array":
        return deserializeArray(domObject);
      case "Function":        
        return deserializeFunction(domObject);      
      default:
        try {
          retObj = eval("new "+ nodeType + "()");
        }
        catch(e) {
          // create generic class
          retObj = {};
        }
      break;
    }
    
    for(var i = 0; i < domObject.childNodes.length; i++) {
      var Node = domObject.childNodes[i];
      retObj[Node.nodeName] = deserial(Node);
    }
  
    return retObj;
  }
  
  /**
   * Check if the current element is one of the primitive data types
   * 
   * @function {private Boolean} isSimpleVar
   * @param {String} type - The "type" attribute of the current node
   * @return {Boolean} Returns true if a boolean or false otherwise
   */
  function isSimpleVar(type)
  {
    switch(type) {
      case "int":
      case "string":
      case "String":
      case "Number":
      case "number":
      case "Boolean":
      case "boolean":
      case "bool":
      case "dateTime":
      case "Date":
      case "date":
      case "float":
        return true;
    }
    
    return false;
  }
  
  /**
   * Convert a string to an object
   * 
   * @function {private Object} stringToObject
   * @param {String} text - The text to parse into the new object
   * @param {String} type - The type of object that you wish to parse TO
   * @return {Object} The Object representation of the string
   */
  function stringToObject(text, type) {
    var retObj = null;
  
    switch(type.toLowerCase())
    {
      case "int":
        return parseInt(text, 10);   
         
      case "number":
        var outNum;
        
        if (text.indexOf(".") > 0) {
          return parseFloat(text);    
        } else {
          return parseInt(text, 10);    
        }      
           
      case "string":
        return text;      
         
      case "dateTime":
      case "date":
        return new Date(text);
          
      case "float":
        return parseFloat(text, 10);
        
      case "bool":
          if (text == "true" || text == "True") {
            return true;
          }
          else {
            return false;
          } 
    }
  
    return retObj;  
  }
  
  /**
   * Get the name of an object by extracting it from it's constructor attribute
   * 
   * @function {private String} getClassName
   * @param {Object} obj - The object for which the name is to be found
   * @return {String} The class name of the object passed in if found
   */
  function getClassName(obj) {   
    try {
      var ClassName = obj.constructor.toString();
      ClassName = ClassName.substring(ClassName.indexOf("function") + 8, ClassName.indexOf('(')).replace(/ /g,'');
      return ClassName;
    }
    catch(e) {
      return "NULL";
    }
  }
  
  /**
   * Get the type of Object by checking against the Built-in objects.
   * If no built in object is found, call getClassName
   * 
   * @function {private String} getTypeName
   * @see getClassName
   * @param {Object} obj - The object for which the type is to be found
   * @return {String} The type of the passed in var
   */ 
  function getTypeName(obj) {
    if (obj instanceof Array) {
      return "array";
    }
      
    if (obj instanceof Date) {
      return "date";  
    }
      
    var type = typeof(obj);
  
    if (isSimpleVar(type)) {
      return type;
    }
    
    type = getClassName(obj); 
    
    return type;
  }
  
  /**
   * Deserialize an Array
   * 
   * @function {private Object} deserializeArray
   * @param {XML String} node - The node to deserialize into an Array
   * @return {Array} The deserialized Array 
   */
  function deserializeArray(node) {
    var retObj = [];
          
    // Cycle through the array's TOP LEVEL children
    while ((child = node.firstChild) != null) {

      // delete child so it's children aren't recursed
      node.removeChild(node.firstChild);
                
      var nodeType = getNodeType(child);
      
      if(isSimpleVar(nodeType)) {
        retObj[retObj.length] = child.textContent;
      } else {
        var tmp = child.textContent;
        if(child.textContent.trim() != '') {
          retObj[retObj.length] = deserial(child);
        }           
      }                   
    }     
    return retObj;      
  }
  
  /**
   * Deserialize a Function
   * 
   * @function {private Function} deserializeFunction
   * @param {XML String} node - The node to deserialize into a Function
   * @return {Function} The deserialized Function
   */ 
  function deserializeFunction(func) {
    if(func && func.textContent) {
      return eval(func.textContent);
    }
  }
  
  /**
   * Get the type attribute of an element if there is one,
   * otherwise return generic 'object'
   * 
   * NB: This function is used on the resulting serialized XML and not on
   *     any actual javascript object
   *     
   * @function {private String} getNodeType    
   * @param {XML} node - The node for which the type is to be found
   * @return {String} The type of the node
   */   
  function getNodeType(node) {
    var nodeType = "object";
    
    if (node.attributes != null && node.attributes.length != 0) {
      var tmp = node.attributes.getNamedItem("type");
      if (tmp != null) {
        nodeType = node.attributes.getNamedItem("type").nodeValue;
      }
    }
    
    return nodeType;  
  } 
};

/**
 * Trim spaces from a string
 * 
 * Usage:  stringObject.trim();
 * 
 * @function {public String} trim
 * @return {String} The trimmed String
 */
if(!String.prototype.trim) {
  String.prototype.trim = function() {
	  a = this.replace(/^\s+/, '');
	  return a.replace(/\s+$/, '');
  };
}