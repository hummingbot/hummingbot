import PropTypes from 'prop-types';
import React, {Component, Fragment} from 'react';
import docs from '../docs.json';
import extend from 'lodash/extend';
import partition from 'lodash/partition';
import remark from 'remark';
import remark2react from 'remark-react';
import styled from '@emotion/styled';
import withProps from 'recompose/withProps';
import {colors, smallCaps} from 'gatsby-theme-apollo-core';
import { TableWrapper, StyledTable } from './template';


const Header = styled.div({});

const MainHeading = styled.h3({
  paddingTop: 20
});

const StyledCode = styled.code({
  padding: '0 !important',
  background: 'none !important'
});

const Subheading = styled.h6({
  marginTop: 12,
  marginBottom: 10
});

const Body = styled.div({});

const BodySubheading = styled.h6(smallCaps, {
  fontWeight: 'bold'
});

function _summary(rawData) {
  if (rawData.comment) {
    return rawData.comment.shortText;
  }
  return (
    rawData.signatures &&
    rawData.signatures[0].comment &&
    rawData.signatures[0].comment.shortText
  );
}

function _isReflectedProperty(data) {
  return (
    data.kindString === 'Property' &&
    data.type &&
    data.type.type === 'reflection'
  );
}

function _parameterString(names, leftDelim, rightDelim) {
  leftDelim = leftDelim || '(';
  rightDelim = rightDelim || ')';
  return leftDelim + names.join(', ') + rightDelim;
}

function _typeId(type) {
  return type.fullName || type.name;
}

function isReadableName(name) {
  return name.substring(0, 2) !== '__';
}

const Code = withProps({
  className: 'language-'
})('code');

function mdToReact(text) {
  const sanitized = text.replace(/\{@link (\w*)\}/g, '[$1](#$1)');
  return remark()
    .use(remark2react, {
      remarkReactComponents: {
        code: Code
      }
    })
    .processSync(sanitized).contents;
}

export class TypescriptApiBox extends Component {
  static propTypes = {
    name: PropTypes.string.isRequired
  };

  get dataByKey() {
    const dataByKey = {};

    function traverse(tree, parentName) {
      let {name} = tree;
      if (['Constructor', 'Method', 'Property'].includes(tree.kindString)) {
        name = `${parentName}.${tree.name}`;
        // add the parentName to the data so we can reference it for ids
        tree.parentName = parentName;
        tree.fullName = name;
      }

      dataByKey[name] = tree;

      if (tree.children) {
        tree.children.forEach(child => {
          traverse(child, name);
        });
      }
    }

    traverse(docs);

    return dataByKey;
  }

  templateArgs(rawData) {
    const parameters = this._parameters(rawData, this.dataByKey);
    const split = partition(parameters, 'isOptions');

    const groups = [];
    if (split[1].length > 0) {
      groups.push({
        name: 'Arguments',
        members: split[1]
      });
    }
    if (split[0].length > 0) {
      groups.push({
        name: 'Options',
        // the properties of the options parameter are the things listed in this group
        members: split[0][0].properties
      });
    }

    if ('Interface' === rawData.kindString) {
      groups.push({
        name: 'Properties',
        members: this._objectProperties(rawData)
      });
    }

    let type;
    if ('Type alias' === rawData.kindString) {
      // this means it's an object type
      if (rawData.type.declaration && rawData.type.declaration.children) {
        groups.push({
          name: 'Properties',
          members: this._objectProperties(rawData.type.declaration)
        });
      } else {
        type = this._type(rawData);
      }
    }

    return {
      id: _typeId(rawData),
      name: rawData.name,
      type,
      signature: this._signature(rawData, parameters),
      summary: _summary(rawData),
      groups,
      repo: 'apollostack/apollo-client',
      filepath: rawData.sources[0].fileName,
      lineno: rawData.sources[0].line
    };
  }

  // This is just literally the name of the type, nothing fancy, except for references
  _typeName = type => {
    if (type.type === 'instrinct') {
      if (type.isArray) {
        return '[' + type.name + ']';
      }
      return type.name;
    } else if (type.type === 'union') {
      const typeNames = [];
      for (let i = 0; i < type.types.length; i++) {
        // Try to get the type name for this type.
        const typeName = this._typeName(type.types[i]);
        // Propogate undefined type names by returning early. Otherwise just add the
        // type name to our array.
        if (typeof typeName === 'undefined') {
          return;
        } else {
          typeNames.push(typeName);
        }
      }
      // Join all of the types together.
      return typeNames.join(' | ');
    } else if (type.type === 'reference') {
      // check to see if the reference type is a simple type alias
      const referencedData = this.dataByKey[type.name];
      if (referencedData && referencedData.kindString === 'Type alias') {
        // Is it an "objecty" type? We can't display it in one line if so
        if (
          !referencedData.type.declaration ||
          !referencedData.type.declaration.children
        ) {
          return this._type(referencedData);
        }
      }

      // it used to be this: return _link(_typeId(type), type.name);
      return _typeId(type);
    } else if (type.type === 'stringLiteral') {
      return '"' + type.value + '"';
    }
  };

  _objectProperties(rawData) {
    const signatures = Array.isArray(rawData.indexSignature)
      ? rawData.indexSignature
      : [];
    return signatures
      .map(signature => {
        const parameterString = this._indexParameterString(signature);
        return extend(this._parameter(signature), {name: parameterString});
      })
      .concat(rawData.children.map(this._parameter));
  }

  _indexParameterString(signature) {
    const parameterNamesAndTypes = signature.parameters.map(
      param => param.name + ':' + this._typeName(param.type)
    );
    return _parameterString(parameterNamesAndTypes, '[', ']');
  }

  // Render the type of a data object. It's pretty confusing, to say the least
  _type = (data, skipSignature) => {
    const {type} = data;

    if (data.kindString === 'Method') {
      return this._type(data.signatures[0]);
    }

    if (data.kindString === 'Call signature' && !skipSignature) {
      const paramTypes = Array.isArray(data.parameters)
        ? data.parameters.map(this._type)
        : [];
      const args = '(' + paramTypes.join(', ') + ')';
      return args + ' => ' + this._type(data, true);
    }

    const isReflected =
      data.kindString === 'Type alias' || type.type === 'reflection';
    if (isReflected && type.declaration) {
      const {declaration} = type;
      if (declaration.signatures) {
        return this._type(declaration.signatures[0]);
      }

      if (declaration.indexSignature) {
        const signature = declaration.indexSignature[0];
        return (
          this._indexParameterString(signature) + ':' + this._type(signature)
        );
      }
    }

    let typeName = this._typeName(type);
    if (!typeName) {
      console.error(
        'unknown type name for',
        data.name,
        'using the type name `any`'
      );
      // console.trace();
      typeName = 'any';
    }

    if (type.typeArguments) {
      return (
        typeName +
        _parameterString(type.typeArguments.map(this._typeName), '<', '>')
      );
    }
    return typeName;
  };

  // XXX: not sure whether to use the 'kind' enum from TS or just run with the
  // strings. Strings seem safe enough I guess
  _signature(rawData, parameters) {
    let dataForSignature = rawData;
    if (_isReflectedProperty(rawData)) {
      dataForSignature = rawData.type.declaration;
    }

    const escapedName = escape(rawData.name);

    // if it is a function, and therefore has arguments
    const signature =
      dataForSignature.signatures && dataForSignature.signatures[0];
    if (signature) {
      const {name} = rawData;
      const parameterString = _parameterString(
        parameters.map(param => param.name)
      );
      let returnType = '';
      if (rawData.kindString !== 'Constructor') {
        const type = this._type(signature, true);
        if (type !== 'void') {
          returnType = ': ' + this._type(signature, true);
        }
      }

      return name + parameterString + returnType;
    }

    return escapedName;
  }

  _parameter = param => ({
    name: param.name,
    type: this._type(param),
    description:
      param.comment && (param.comment.text || param.comment.shortText)
  });

  // Takes the data about a function / constructor and parses out the named params
  _parameters(rawData, dataByKey) {
    if (_isReflectedProperty(rawData)) {
      return this._parameters(rawData.type.declaration, dataByKey);
    }

    const signature = rawData.signatures && rawData.signatures[0];
    if (!signature || !Array.isArray(signature.parameters)) {
      return [];
    }

    return signature.parameters.map(param => {
      let name;
      if (isReadableName(param.name)) {
        name = param.name; // eslint-disable-line prefer-destructuring
      } else if (isReadableName(param.originalName)) {
        name = param.originalName;
      } else {
        // XXX: not sure if this is the correct logic, but it feel OK
        name = 'options';
      }

      let properties = [];
      if (param.type && param.type.declaration) {
        properties = Array.isArray(param.type.declaration.children)
          ? param.type.declaration.children.map(this._parameter)
          : [];
      } else if (param.type && param.type.type === 'reference') {
        const dataForProperties = dataByKey[param.type.name] || {};
        properties = Array.isArray(dataForProperties.children)
          ? dataForProperties.children.map(this._parameter)
          : [];
      }

      return extend(this._parameter(param), {
        name,
        isOptions: name === 'options',
        optional: !!param.defaultValue,
        properties
      });
    });
  }

  render() {
    const rawData = this.dataByKey[this.props.name];
    if (typeof rawData === 'undefined') {
      // TODO: account for things that past versions may reference, but have
      // been removed in current version docs.json
      return null;
    }

    const args = this.templateArgs(rawData);
    return (
      <>
        <Header>
          <MainHeading title={args.name} id={args.id}>
            <StyledCode className="language-">
              <a href={`#${args.id}`}>{args.signature}</a>
            </StyledCode>
          </MainHeading>
          {args.filepath && (
            <Subheading>
              <a
                href={`https://github.com/${args.repo}/blob/master/${args.filepath}#L${args.lineno}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                ({args.filepath}, line {args.lineno})
              </a>
            </Subheading>
          )}
        </Header>
        <Body>
          {args.summary && mdToReact(args.summary)}
          {args.type && <div>{args.type}</div>}
          {args.groups
            .filter(group => group.members.length)
            .map((group, index) => (
              <Fragment key={index}>
                <BodySubheading>{group.name}</BodySubheading>
                <TableWrapper>
                  <StyledTable className="field-table">
                    <thead>
                      <tr>
                        <th>Name /<br/>Type</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.members.map((member, index) => (
                        <tr>
                          <td>
                            <h6><StyledCode className="language-">{member.name}</StyledCode></h6>
                            <p><StyledCode className="language-">{member.type}</StyledCode></p>
                          </td>
                          <td>
                            {member.description && mdToReact(member.description)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </StyledTable>
                </TableWrapper>
              </Fragment>
            ))}
        </Body>
        </>
    );
  }
}
