pipeline {
  agent any

  environment {
    IMAGE_NAME = "demo-flask"
    CONTAINER_NAME = "demo-flask-app"
    PORT = "5000"
  }

  stages {
    stage("Checkout") {
      steps {
        checkout scm
      }
    }

    stage("Build Docker Image") {
      steps {
        sh "docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} ."
        sh "docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest"
      }
    }

    stage("Test (basic)") {
      steps {
        sh "docker run --rm ${IMAGE_NAME}:latest python -c \"import flask; print('OK')\""
      }
    }

    stage("Deploy (run container)") {
      steps {
        sh """
          docker rm -f ${CONTAINER_NAME} || true
          docker run -d --name ${CONTAINER_NAME} -p ${PORT}:${PORT} ${IMAGE_NAME}:latest
        """
      }
    }
  }

  post {
    always {
      sh "docker image ls | head -n 10"
    }
  }
}
