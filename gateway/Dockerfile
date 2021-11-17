FROM node:16.3.0

# Set labels
LABEL application="gateway-v2"
LABEL branch=${BRANCH}
LABEL commit=${COMMIT}
LABEL date=${BUILD_DATE}

# Set ENV variables
ENV COMMIT_BRANCH=${BRANCH}
ENV COMMIT_SHA=${COMMIT}
ENV BUILD_DATE=${DATE}

# app directory
WORKDIR /usr/src/app

# install dependancies
COPY package*.json ./
# COPY yarn.lock ./

RUN yarn

# copy pwd file to container
COPY . .

EXPOSE 5000

RUN yarn build

CMD ["yarn", "run", "start"]
